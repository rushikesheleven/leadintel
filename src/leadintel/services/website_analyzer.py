"""
Website Analyzer Service.

Comprehensive website diagnostic service:
- Checks availability, response time, and HTTP status.
- Detects HTTP vs HTTPS and verifies SSL/TLS validity.
- Extracts page title, meta description, and viewport configuration.
- Detects H1, H2, and image alt presence.
- Detects contact details (emails, phone numbers, contact forms).
- Detects social media links.
- Samples and checks internal links for 404/broken status where practical.
- Protects against SSRF, respects robots.txt, and enforces size/rate limits.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .robots_checker import RobotsChecker
from .social_finder import extract_social_profiles
from .url_validator import create_safe_client, validate_and_normalize_url

logger = logging.getLogger(__name__)

USER_AGENT = "LeadIntel/0.1 (Business Intelligence Researcher; +https://github.com/example/leadintel; respectful crawler)"
MAX_HTML_BYTES = 5_000_000  # 5MB max payload limit
MAX_BROKEN_LINKS_CHECK = 10  # Maximum number of internal links to spot-check for broken links

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,9}")


async def analyze_target_website(
    url: str,
    check_broken_links: bool = True,
    client: Optional[httpx.AsyncClient] = None,
) -> dict[str, Any]:
    """
    Perform a complete website analysis on the given URL.

    Returns structured diagnostics or error details.
    """
    norm_url = validate_and_normalize_url(url)

    # 1. Check robots.txt
    robots = RobotsChecker()
    can_fetch, reason = await robots.can_fetch(norm_url)
    if not can_fetch:
        return {
            "status": "blocked_by_robots",
            "url": norm_url,
            "available": False,
            "error": reason or "Blocked by website robots.txt policy.",
        }

    should_close = False
    if client is None:
        client = create_safe_client(timeout=15.0)
        should_close = True

    try:
        # Fetch page with streaming or byte cap
        start_time = asyncio.get_event_loop().time()
        try:
            resp = await client.get(
                norm_url,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            )
            elapsed = round(asyncio.get_event_loop().time() - start_time, 3)
        except Exception as exc:
            logger.debug("Failed to fetch target website %s: %s", norm_url, exc)
            return {
                "status": "error",
                "url": norm_url,
                "available": False,
                "error": f"Connection failed or timed out: {exc}",
            }

        # Content length safeguard
        raw_bytes = resp.content
        if len(raw_bytes) > MAX_HTML_BYTES:
            raw_bytes = raw_bytes[:MAX_HTML_BYTES]

        html = raw_bytes.decode(resp.encoding or "utf-8", errors="replace")

        # 2. SSL / Protocol Checks
        final_url = str(resp.url)
        is_https = final_url.startswith("https://")
        ssl_valid = is_https  # If httpx connects over https with standard ssl verify=True without exception, it is valid

        # 3. HTML Extraction via BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        title_tag = soup.find("title")
        title = title_tag.get_text().strip() if title_tag else None

        desc_tag = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "description"})
        meta_description = desc_tag.get("content", "").strip() if desc_tag else None

        viewport_tag = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "viewport"})
        has_mobile_viewport = bool(viewport_tag and "width=" in viewport_tag.get("content", "").lower())

        # Headings & Media
        h1_tags = [h.get_text().strip() for h in soup.find_all("h1") if h.get_text().strip()]
        h2_tags = [h.get_text().strip() for h in soup.find_all("h2") if h.get_text().strip()]
        images = soup.find_all("img")
        images_missing_alt = [img for img in images if not img.get("alt") or not img.get("alt").strip()]

        # 4. Contact Detection (Emails, Phone numbers, Forms)
        contact_forms = soup.find_all("form")
        has_contact_form = False
        for f in contact_forms:
            form_text = str(f).lower()
            if any(term in form_text for term in ("contact", "email", "message", "inquiry", "send", "submit")):
                has_contact_form = True
                break

        # Search for mailto / tel links first
        emails: set[str] = set()
        phones: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.lower().startswith("mailto:"):
                clean_email = href[7:].split("?")[0].strip()
                if EMAIL_REGEX.match(clean_email):
                    emails.add(clean_email)
            elif href.lower().startswith("tel:"):
                clean_tel = href[4:].split("?")[0].strip()
                if len(clean_tel) >= 7:
                    phones.add(clean_tel)

        # Secondary regex search in body text (exclude scripts/styles)
        for s in soup(["script", "style", "noscript"]):
            s.decompose()
        body_text = soup.get_text()

        for em in EMAIL_REGEX.findall(body_text):
            if not em.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif")):
                emails.add(em)
                if len(emails) >= 5:
                    break

        # 5. Social Profiles
        social_profiles = extract_social_profiles(html, base_url=final_url)

        # 6. Internal / Broken Links Spot-Check
        base_domain = urlparse(final_url).netloc.lower()
        internal_links_to_check: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            full_link = urljoin(final_url, href)
            p_link = urlparse(full_link)
            if p_link.netloc.lower() == base_domain and full_link != final_url:
                if full_link not in internal_links_to_check:
                    internal_links_to_check.append(full_link)
            if len(internal_links_to_check) >= MAX_BROKEN_LINKS_CHECK:
                break

        broken_links: list[dict[str, Any]] = []
        if check_broken_links and internal_links_to_check:
            for link in internal_links_to_check[:MAX_BROKEN_LINKS_CHECK]:
                try:
                    head_resp = await client.head(link, timeout=5.0)
                    if head_resp.status_code >= 400:
                        broken_links.append({"url": link, "status_code": head_resp.status_code})
                except Exception as e:
                    broken_links.append({"url": link, "error": str(e)})

        return {
            "status": "success",
            "url": final_url,
            "available": resp.status_code < 400,
            "http_status": resp.status_code,
            "response_time_seconds": elapsed,
            "protocol": {
                "is_https": is_https,
                "ssl_valid": ssl_valid,
                "redirected": str(resp.url) != norm_url,
            },
            "metadata": {
                "title": title,
                "meta_description": meta_description,
                "has_mobile_viewport": has_mobile_viewport,
            },
            "content_structure": {
                "h1_headings": h1_tags,
                "h2_headings_sample": h2_tags[:5],
                "h2_count": len(h2_tags),
                "images_total": len(images),
                "images_missing_alt": len(images_missing_alt),
            },
            "contact_detection": {
                "has_contact_form": has_contact_form,
                "emails_found": list(emails)[:5],
                "phones_found": list(phones)[:5],
            },
            "social_profiles": social_profiles,
            "broken_internal_links": broken_links,
        }

    finally:
        if should_close:
            await client.aclose()
