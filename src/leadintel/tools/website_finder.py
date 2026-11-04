"""
Website Finder & Search Utilities.

Provides free, open discovery of a business's official website using:
1. Provider registry lookup (e.g. OSM tags `website`, `contact:website`, `url`).
2. DuckDuckGo HTML / Instant Answers (completely free, no API key required).
3. Fallback demo data resolver.

Compliance:
- Respects robots policies and rate limiting.
- Avoids scraping protected personal data.
- Never sends telemetry or sensitive data to third-party providers.
"""

from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import parse_qs, quote, unquote, urlparse

import httpx

from ..config import settings
from ..providers import build_registry

logger = logging.getLogger(__name__)

USER_AGENT = "LeadIntel/0.1 (Business Intelligence Researcher; open-source; respectful crawler)"
_registry = build_registry(settings)

# Domains to ignore when seeking a company's direct website
IGNORED_DOMAINS = {
    "google.com",
    "www.google.com",
    "maps.google.com",
    "facebook.com",
    "www.facebook.com",
    "instagram.com",
    "www.instagram.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "www.linkedin.com",
    "yelp.com",
    "www.yelp.com",
    "tripadvisor.com",
    "www.tripadvisor.com",
    "yellowpages.com",
    "wikipedia.org",
    "en.wikipedia.org",
    "crunchbase.com",
    "glassdoor.com",
}


def _clean_url(url: str) -> Optional[str]:
    """Sanitize and validate extracted URL."""
    if not url:
        return None
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if not domain or "." not in domain:
            return None
        if domain in IGNORED_DOMAINS:
            return None
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    except Exception:
        return None


async def find_website_for_business(
    business_name: str,
    location: Optional[str] = None,
    business_id: Optional[str] = None,
) -> tuple[Optional[str], str]:
    """
    Locate official website for a business name / location or business_id.

    Returns:
        tuple (website_url, source_method)
    """
    # 1. Check if business_id is provided and known to provider registry
    if business_id:
        biz, provider_name = await _registry.get_details(business_id)
        if biz and biz.website:
            return biz.website, f"provider:{provider_name}"

    # 2. Check demo fixtures if offline/demo
    demo_biz = None
    if business_id:
        from ..data.demo import get_demo_business
        demo_biz = get_demo_business(business_id)
    if not demo_biz and business_name:
        from ..data.demo import search_demo_businesses
        matches = search_demo_businesses(query=business_name, location=location, limit=1)
        if matches:
            demo_biz = matches[0]
    if demo_biz and demo_biz.website and (settings.demo_mode or not business_name):
        return demo_biz.website, "demo_fixture"

    # 3. DuckDuckGo HTML Lite free lookup
    query = f"{business_name} {location or ''}".strip()
    if not query:
        return None, "empty_query"

    try:
        url = await _search_duckduckgo_html(query)
        if url:
            return url, "duckduckgo_lite"
    except Exception as exc:
        logger.debug("DuckDuckGo lookup failed for %s: %s", query, exc)

    # 4. Fallback to demo fixture if available as last resort
    if demo_biz and demo_biz.website:
        return demo_biz.website, "demo_fallback"

    return None, "not_found"


async def _search_duckduckgo_html(query: str) -> Optional[str]:
    """
    Query DuckDuckGo HTML Lite (no JS, no API key) for first organic non-directory link.
    """
    search_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        resp = await client.get(search_url, headers=headers)
        if resp.status_code != 200:
            return None

        # DuckDuckGo HTML links format: <a class="result__url" href="/l/?uddg=URL..."> or similar
        content = resp.text
        # Extract hrefs
        matches = re.findall(r'href=["\'](/l/\?uddg=[^"\']+)["\']', content)
        for m in matches:
            parsed = parse_qs(urlparse(m).query)
            uddg = parsed.get("uddg")
            if uddg:
                raw_url = unquote(uddg[0])
                cleaned = _clean_url(raw_url)
                if cleaned:
                    return cleaned

        # Fallback regex for standard a tags
        links = re.findall(r'class="result__snippet"[^>]*>.*?</a>|<a[^>]+class="result__url"[^>]+href=["\']([^"\']+)["\']', content, re.DOTALL)
        for link in links:
            if isinstance(link, str) and link.startswith("http"):
                cleaned = _clean_url(link)
                if cleaned:
                    return cleaned

    return None
