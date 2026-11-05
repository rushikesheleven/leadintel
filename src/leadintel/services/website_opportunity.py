"""
Website Opportunity Identification & Digital Verification Service.

Identifies website opportunities for local businesses:
- Checks OSM website field.
- If missing or unverified, performs web research to look for an official website.
- Verifies whether discovered websites belong to the business (token/name matching).
- Distinguishes official websites from directories, aggregators, and social profiles.
- Validates website accessibility and basic performance via safe HTTP clients.
- Assigns deterministic website_status and website_opportunity_score (0–100 scale).

Status States:
- 'website_verified': Official active website confirmed.
- 'website_not_found_after_research': No official website found after web research.
- 'website_unverified': Discovered domain cannot be confirmed as belonging to business.
- 'website_broken': Website is configured but unreachable or returning error codes.
- 'website_not_checked': OSM website field is empty and research was not requested.

Scoring Scale:
- No website found after research: 90–100 (default: 95.0)
- Broken website: 75–89 (default: 80.0)
- Weak / outdated website: 50–74 (default: 65.0)
- Significant SEO problems: 30–49 (default: 40.0)
- Good website: 5–29 (default: 15.0)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Optional
from urllib.parse import parse_qs, quote, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from ..models.business import Business
from .url_validator import create_safe_client, validate_and_normalize_url

logger = logging.getLogger(__name__)

USER_AGENT = "LeadIntel/0.2.0 (Business Intelligence Researcher; open-source; respectful crawler)"

# ── Directory & Aggregator Domains ───────────────────────────────────────────
DIRECTORY_AND_AGGREGATOR_DOMAINS = {
    # Global directories & review portals
    "yelp.com",
    "tripadvisor.com",
    "yellowpages.com",
    "wikipedia.org",
    "crunchbase.com",
    "glassdoor.com",
    "foursquare.com",
    "trustpilot.com",
    "bbb.org",
    "mapquest.com",
    "superpages.com",
    "angis.com",
    "thumbtack.com",
    "manta.com",
    "merchantcircle.com",
    "citysearch.com",
    "ezlocal.com",
    "hotfrog.com",
    # Search engines & map platforms
    "google.com",
    "maps.google.com",
    "bing.com",
    "yahoo.com",
    "duckduckgo.com",
    "baidu.com",
    "yandex.com",
    # Indian directories, food & commercial aggregators (critical for Pune & India)
    "justdial.com",
    "sulekha.com",
    "indiamart.com",
    "tradeindia.com",
    "zomato.com",
    "swiggy.com",
    "magicpin.in",
    "dineout.co.in",
    "lbb.in",
    "eattreat.in",
    "burrp.com",
    "mouthshut.com",
    "urbancompany.com",
    "housing.com",
    "99acres.com",
    "magicbricks.com",
    "quikr.com",
    "olx.in",
    "practo.com",
    "lybrate.com",
    "nearbuy.com",
    "dialme.in",
    "asklaila.com",
    "eatsure.com",
}

# ── Social Media Domains ─────────────────────────────────────────────────────
SOCIAL_DOMAINS = {
    "facebook.com",
    "fb.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "youtube.com",
    "pinterest.com",
    "tiktok.com",
    "threads.net",
    "whatsapp.com",
    "t.me",
    "telegram.org",
}

# In-memory research cache: query -> (candidate_url, timestamp)
_RESEARCH_CACHE: dict[str, tuple[Optional[str], float]] = {}
_RESEARCH_CACHE_TTL = 3600.0  # 1 hour


def extract_domain(url: str) -> str:
    """Extract normalized base domain from a URL."""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = (parsed.netloc or "").lower().split(":")[0].strip()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def is_directory_or_social_domain(url_or_domain: str) -> bool:
    """Check if a URL or domain belongs to a directory, aggregator, or social network."""
    domain = extract_domain(url_or_domain)
    if not domain:
        return False

    # Check exact match or subdomain
    for d in DIRECTORY_AND_AGGREGATOR_DOMAINS:
        if domain == d or domain.endswith(f".{d}"):
            return True

    for s in SOCIAL_DOMAINS:
        if domain == s or domain.endswith(f".{s}"):
            return True

    return False


def is_domain_belonging_to_business(
    domain: str, business_name: str, location: Optional[str] = None
) -> bool:
    """
    Check if a discovered domain plausibly belongs to the business.

    Matches significant tokens from the business name against the domain name.
    """
    if location and domain:
        loc_lower = location.lower()
        # Reject UK domains for India/Pune searches
        if domain.endswith(".co.uk") and not any(x in loc_lower for x in ["uk", "united kingdom", "london"]):
            return False
        # Reject AU domains for India/Pune searches
        if domain.endswith(".com.au") and not any(x in loc_lower for x in ["au", "australia", "sydney"]):
            return False

    if not domain or not business_name:
        return False

    # Normalize business name tokens
    name_clean = re.sub(r"[^\w\s]", " ", business_name.lower())
    tokens = [t.strip() for t in name_clean.split() if len(t.strip()) >= 3]

    # Stopwords to discard
    stopwords = {
        "pvt", "ltd", "limited", "inc", "corp", "corporation", "co", "the",
        "and", "services", "solutions", "enterprise", "group", "company",
        "hotel", "restaurant", "cafe", "bistro", "shop", "store",
    }
    significant_tokens = [t for t in tokens if t not in stopwords]
    if not significant_tokens:
        significant_tokens = tokens  # fallback to all tokens if all were stopwords

    # Clean domain base (e.g. 'vaishalihotel' from 'vaishalihotel.in')
    domain_base = domain.split(".")[0].lower()

    for token in significant_tokens:
        if token in domain_base or domain_base in token:
            return True

    # Check whole compacted business name
    compacted_name = "".join(significant_tokens)
    if compacted_name and (compacted_name in domain_base or domain_base in compacted_name):
        return True

    return False


async def search_official_website(
    business_name: str,
    location: Optional[str] = None,
) -> Optional[str]:
    """
    Search for a business's official website using free DuckDuckGo HTML search.
    Caches queries to respect rate limits.
    """
    query = f"{business_name} {location or ''}".strip()
    if not query:
        return None

    cache_key = query.lower()
    cached = _RESEARCH_CACHE.get(cache_key)
    if cached is not None:
        url, ts = cached
        if time.monotonic() - ts < _RESEARCH_CACHE_TTL:
            return url

    search_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    candidate: Optional[str] = None
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True, limits=limits) as client:
            resp = await client.get(search_url, headers=headers)
            if resp.status_code == 200:
                content = resp.text
                matches = re.findall(r'href=["\'](/l/\?uddg=[^"\']+)["\']', content)
                for m in matches:
                    parsed = parse_qs(urlparse(m).query)
                    uddg = parsed.get("uddg")
                    if uddg:
                        raw_url = unquote(uddg[0])
                        domain = extract_domain(raw_url)
                        if not domain or is_directory_or_social_domain(domain):
                            continue
                        if is_domain_belonging_to_business(domain, business_name, location):
                            candidate = raw_url
                            break
    except Exception as exc:
        logger.debug("Web research search failed for '%s': %s", query, exc)

    _RESEARCH_CACHE[cache_key] = (candidate, time.monotonic())
    return candidate


async def evaluate_business_website(
    biz: Business,
    location: Optional[str] = None,
    research_missing: bool = True,
    client: Optional[httpx.AsyncClient] = None,
) -> Business:
    """
    Diagnose website presence and calculate website_opportunity_score.

    Modifies and returns the Business instance.
    """
    website_url = biz.website

    # 1. Check if existing website is actually a directory or social profile
    if website_url:
        if is_directory_or_social_domain(website_url):
            logger.debug(
                "Business '%s' has directory/social URL '%s' as website. Treating as missing official website.",
                biz.name,
                website_url,
            )
            # Store in social profile if applicable
            domain = extract_domain(website_url)
            if "instagram" in domain:
                biz.twitter_url = biz.twitter_url  # keep
            elif "facebook" in domain:
                biz.facebook_url = website_url
            elif "linkedin" in domain:
                biz.linkedin_url = website_url

            biz.website = None
            website_url = None

    # 2. If website is missing, decide whether to research or mark website_not_checked
    if not website_url:
        if not research_missing:
            biz.website_status = "website_not_checked"
            biz.website_opportunity_score = None
            biz.website_opportunity_explanation = (
                "OSM website field is empty; web research was not requested."
            )
            return biz

        # Perform research
        found_url = await search_official_website(biz.name, location=location or biz.city)
        if found_url:
            website_url = found_url
            biz.website = found_url
        else:
            biz.website_status = "website_not_found_after_research"
            biz.website_opportunity_score = 95.0
            biz.website_opportunity_explanation = (
                "No official website found after thorough web research across search engines "
                "and business directories. Prime candidate for website development services."
            )
            return biz

    # 3. We have a candidate website URL — verify and inspect accessibility
    domain = extract_domain(website_url)
    if not is_domain_belonging_to_business(domain, biz.name, location):
        biz.website_status = "website_unverified"
        biz.website_opportunity_score = 55.0
        biz.website_opportunity_explanation = (
            f"Website domain '{domain}' could not be definitively verified as belonging to {biz.name}."
        )
        return biz

    # Validate URL structure and normalize
    try:
        norm_url = validate_and_normalize_url(website_url)
    except Exception as exc:
        biz.website_status = "website_broken"
        biz.website_opportunity_score = 80.0
        biz.website_opportunity_explanation = f"Website URL is invalid or unsafe: {exc}"
        return biz

    # Safe HTTP fetch to test accessibility and basic SEO
    should_close = False
    if client is None:
        client = create_safe_client(timeout=6.0)
        should_close = True

    MAX_RESPONSE_BYTES = 200_000

    try:
        start_t = time.monotonic()
        async with client.stream(
            "GET",
            norm_url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        ) as resp:
            resp_time = round(time.monotonic() - start_t, 2)

            if resp.status_code >= 400:
                biz.website_status = "website_broken"
                biz.website_opportunity_score = 80.0
                biz.website_opportunity_explanation = (
                    f"Website returned HTTP error {resp.status_code} ({norm_url})."
                )
                return biz

            chunks: list[bytes] = []
            total_bytes = 0
            async for chunk in resp.aiter_bytes():
                chunks.append(chunk)
                total_bytes += len(chunk)
                if total_bytes >= MAX_RESPONSE_BYTES:
                    break

            raw_bytes = b"".join(chunks)[:MAX_RESPONSE_BYTES]
            html = raw_bytes.decode("utf-8", errors="ignore")
            is_https = str(resp.url).startswith("https://")

        soup = BeautifulSoup(html, "html.parser")

        # CMS Footprint Detection
        html_lower = html.lower()
        if "wp-content" in html or "wp-content" in html_lower:
            biz.detected_cms = "WordPress"
        elif "cdn.shopify.com" in html or "cdn.shopify.com" in html_lower:
            biz.detected_cms = "Shopify"
        elif "wix.com" in html or "wixsite" in html or "wix.com" in html_lower or "wixsite" in html_lower:
            biz.detected_cms = "Wix"
        elif "squarespace" in html or "squarespace" in html_lower:
            biz.detected_cms = "Squarespace"

        # Contact Route Detection
        has_contact = False
        for a in soup.find_all("a", href=True):
            href_val = a.get("href")
            if isinstance(href_val, str):
                href_lower = href_val.lower()
                if "contact" in href_lower or "about" in href_lower or "mailto:" in href_lower:
                    has_contact = True
                    break
        biz.has_contact_route = has_contact

        extra_notes: list[str] = []
        if biz.detected_cms:
            extra_notes.append(f"Built on {biz.detected_cms}.")
        if not biz.has_contact_route:
            extra_notes.append("Missing a clear contact page.")
        enrichment = f" {' '.join(extra_notes)}" if extra_notes else ""

        has_viewport = bool(soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)}))
        has_title = bool(soup.find("title") and soup.find("title").get_text(strip=True))
        has_meta_desc = bool(soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)}))

        # Classify website quality
        if not is_https or not has_viewport:
            biz.website_status = "website_verified"
            biz.website_opportunity_score = 65.0
            issues = []
            if not is_https:
                issues.append("missing HTTPS/SSL security")
            if not has_viewport:
                issues.append("missing mobile viewport configuration")
            biz.website_opportunity_explanation = (
                f"Website is active but outdated ({', '.join(issues)}). "
                f"Good opportunity for website redesign / modernization.{enrichment}"
            )
        elif not has_title or not has_meta_desc or resp_time > 2.5:
            biz.website_status = "website_verified"
            biz.website_opportunity_score = 40.0
            issues = []
            if not has_meta_desc:
                issues.append("missing meta description")
            if not has_title:
                issues.append("missing title tag")
            if resp_time > 2.5:
                issues.append(f"slow response time ({resp_time}s)")
            biz.website_opportunity_explanation = (
                f"Website is modern and mobile-ready, but has technical SEO deficiencies ({', '.join(issues)}).{enrichment}"
            )
        else:
            biz.website_status = "website_verified"
            biz.website_opportunity_score = 15.0
            biz.website_opportunity_explanation = (
                f"Website is fast ({resp_time}s), secured with HTTPS, and mobile-responsive.{enrichment}"
            )

    except Exception as exc:
        biz.website_status = "website_broken"
        biz.website_opportunity_score = 80.0
        biz.website_opportunity_explanation = f"Website is unreachable or connection failed: {exc}"
    finally:
        if should_close:
            await client.aclose()

    return biz


async def batch_evaluate_websites(
    businesses: list[Business],
    location: Optional[str] = None,
    research_missing: bool = True,
    max_concurrent: int = 5,
    global_timeout: float = 20.0,
) -> list[Business]:
    """
    Concurrently evaluate websites for a list of businesses with limited concurrency
    and a global timeout to protect against MCP tool timeouts.
    """
    if not businesses:
        return []

    sem = asyncio.Semaphore(max_concurrent)
    client = create_safe_client(timeout=6.0)

    async def _safe_eval(biz: Business) -> Business:
        async with sem:
            try:
                return await evaluate_business_website(
                    biz,
                    location=location,
                    research_missing=research_missing,
                    client=client,
                )
            except Exception as exc:
                logger.warning("Error evaluating website for '%s': %s", biz.name, exc)
                return biz

    try:
        task_to_biz: dict[asyncio.Task[Business], Business] = {}
        for b in businesses:
            task = asyncio.create_task(_safe_eval(b))
            task_to_biz[task] = b

        done, pending = await asyncio.wait(
            task_to_biz.keys(),
            timeout=global_timeout,
        )

        results_by_id: dict[str, Business] = {}

        for t in done:
            original_biz = task_to_biz[t]
            try:
                if not t.cancelled() and t.exception() is None:
                    res_biz = t.result()
                    results_by_id[res_biz.id] = res_biz
                else:
                    results_by_id[original_biz.id] = original_biz
            except Exception as exc:
                logger.warning("Task execution error for '%s': %s", original_biz.name, exc)
                results_by_id[original_biz.id] = original_biz

        if pending:
            logger.warning(
                "Global timeout of %.1fs reached during batch website evaluation; cancelling %d pending task(s).",
                global_timeout,
                len(pending),
            )
            for t in pending:
                t.cancel()
                original_biz = task_to_biz[t]
                original_biz.website_status = "website_not_checked"
                original_biz.website_opportunity_score = None
                original_biz.website_opportunity_explanation = (
                    "Website research aborted to prevent system timeout."
                )
                results_by_id[original_biz.id] = original_biz

            await asyncio.gather(*pending, return_exceptions=True)

        return [results_by_id.get(b.id, b) for b in businesses]
    finally:
        await client.aclose()

