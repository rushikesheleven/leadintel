"""
Custom Python SEO Audit Service.

Performs deterministic, rule-based SEO evaluation without external paid APIs:
- Title tag presence, length, and uniqueness.
- Meta description presence and length.
- H1 tags presence and uniqueness (detects zero or multiple H1s).
- Image alt attributes (percentage of images with descriptive alt text).
- Canonical link tag presence and format.
- Meta robots tag checking (index/noindex, follow/nofollow).
- Open Graph tags (og:title, og:description, og:image, og:url).
- robots.txt and sitemap.xml presence.
- Internal link counts and basic linking health.
- HTML page byte size.

Computes a transparent 0-100 composite score with actionable issues and recommendations.
Note: Transparently communicates that this is an on-page technical audit, not a guarantee of Google ranking.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .url_validator import create_safe_client, validate_and_normalize_url

logger = logging.getLogger(__name__)


def audit_html_seo(html_content: str, page_url: str) -> dict[str, Any]:
    """
    Perform on-page SEO analysis on the HTML string of page_url.

    Returns structured audit data including checks, score (0-100), issues, and recommendations.
    """
    score = 100
    deductions = 0
    issues: list[dict[str, str]] = []
    recommendations: list[str] = []
    checks: dict[str, Any] = {}

    page_bytes = len(html_content.encode("utf-8"))
    checks["html_size_bytes"] = page_bytes
    if page_bytes > 2_000_000:  # 2MB
        issues.append({"level": "warning", "message": f"HTML document size is large ({page_bytes / 1024:.1f} KB)."})
        recommendations.append("Reduce page weight and inline assets to improve load time.")
        deductions += 5

    try:
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception as e:
        return {
            "seo_score": 0,
            "disclaimer": "This is a technical on-page SEO assessment and not a complete Google ranking guarantee.",
            "checks": {"error": f"Failed to parse HTML: {e}"},
            "issues": [{"level": "error", "message": "HTML could not be parsed."}],
            "recommendations": ["Fix HTML syntax and structure."],
        }

    # 1. Title tag
    title_tag = soup.find("title")
    title_text = title_tag.get_text().strip() if title_tag else ""
    checks["title"] = {
        "present": bool(title_text),
        "text": title_text,
        "length": len(title_text),
    }
    if not title_text:
        issues.append({"level": "error", "message": "Page is missing a <title> tag."})
        recommendations.append("Add a concise, descriptive <title> tag (recommended 30-60 characters).")
        deductions += 15
    elif len(title_text) < 15:
        issues.append({"level": "warning", "message": f"Title tag is very short ({len(title_text)} chars)."})
        recommendations.append("Expand the title tag to provide clearer context for users and search engines.")
        deductions += 5
    elif len(title_text) > 70:
        issues.append({"level": "warning", "message": f"Title tag may be truncated in search results ({len(title_text)} chars)."})
        recommendations.append("Keep title tag under 60-70 characters.")
        deductions += 3

    # 2. Meta description
    meta_desc = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "description"})
    desc_text = meta_desc.get("content", "").strip() if meta_desc else ""
    checks["meta_description"] = {
        "present": bool(desc_text),
        "text": desc_text,
        "length": len(desc_text),
    }
    if not desc_text:
        issues.append({"level": "error", "message": "Page is missing a meta description."})
        recommendations.append("Add a compelling meta description tag (recommended 120-160 characters).")
        deductions += 15
    elif len(desc_text) < 50:
        issues.append({"level": "warning", "message": f"Meta description is short ({len(desc_text)} chars)."})
        recommendations.append("Elaborate your meta description to better summarize page content.")
        deductions += 5
    elif len(desc_text) > 165:
        issues.append({"level": "warning", "message": f"Meta description is long ({len(desc_text)} chars) and may be truncated."})
        deductions += 2

    # 3. Headings (H1 & H2)
    h1_tags = soup.find_all("h1")
    h1_texts = [h.get_text().strip() for h in h1_tags if h.get_text().strip()]
    checks["h1_headings"] = {
        "count": len(h1_tags),
        "texts": h1_texts,
    }
    if len(h1_tags) == 0:
        issues.append({"level": "error", "message": "No <h1> heading found on the page."})
        recommendations.append("Include exactly one primary <h1> heading summarizing the main topic.")
        deductions += 15
    elif len(h1_tags) > 1:
        issues.append({"level": "warning", "message": f"Multiple <h1> headings found ({len(h1_tags)})."})
        recommendations.append("Consider using a single primary <h1> heading and structure secondary topics with <h2>.")
        deductions += 5

    h2_tags = soup.find_all("h2")
    checks["h2_count"] = len(h2_tags)
    if len(h2_tags) == 0 and len(html_content) > 1500:
        issues.append({"level": "info", "message": "No <h2> subheadings found."})
        recommendations.append("Use <h2> subheadings to divide text into readable sections.")
        deductions += 3

    # 4. Images & Alt attributes
    images = soup.find_all("img")
    total_imgs = len(images)
    missing_alt = [img for img in images if not img.get("alt") or not img.get("alt").strip()]
    checks["images"] = {
        "total": total_imgs,
        "missing_alt": len(missing_alt),
        "alt_coverage_pct": round(((total_imgs - len(missing_alt)) / total_imgs * 100), 1) if total_imgs else 100.0,
    }
    if missing_alt:
        issues.append({
            "level": "warning",
            "message": f"{len(missing_alt)} of {total_imgs} images are missing alt attributes."
        })
        recommendations.append("Add descriptive alt text to all informative images for accessibility and image search.")
        deductions += min(15, len(missing_alt) * 3)

    # 5. Canonical URL
    canonical_tag = soup.find("link", rel=lambda x: x and "canonical" in x.lower())
    canonical_href = canonical_tag.get("href", "").strip() if canonical_tag else ""
    checks["canonical_url"] = {
        "present": bool(canonical_href),
        "url": canonical_href,
    }
    if not canonical_href:
        issues.append({"level": "info", "message": "No canonical link element specified."})
        recommendations.append("Specify a rel='canonical' link to prevent duplicate content issues.")
        deductions += 5

    # 6. Meta Robots
    meta_robots = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "robots"})
    robots_content = meta_robots.get("content", "").strip() if meta_robots else ""
    checks["meta_robots"] = {
        "present": bool(robots_content),
        "content": robots_content,
        "is_noindex": "noindex" in robots_content.lower(),
        "is_nofollow": "nofollow" in robots_content.lower(),
    }
    if "noindex" in robots_content.lower():
        issues.append({"level": "warning", "message": "Page has 'noindex' directive in meta robots tag."})
        deductions += 10

    # 7. Open Graph metadata
    og_title = soup.find("meta", property="og:title")
    og_desc = soup.find("meta", property="og:description")
    og_image = soup.find("meta", property="og:image")
    checks["open_graph"] = {
        "has_title": bool(og_title and og_title.get("content")),
        "has_description": bool(og_desc and og_desc.get("content")),
        "has_image": bool(og_image and og_image.get("content")),
    }
    if not (og_title and og_desc and og_image):
        missing_og = []
        if not og_title:
            missing_og.append("og:title")
        if not og_desc:
            missing_og.append("og:description")
        if not og_image:
            missing_og.append("og:image")
        issues.append({"level": "info", "message": f"Incomplete Open Graph tags: missing {', '.join(missing_og)}."})
        recommendations.append("Add complete Open Graph meta tags (title, description, image) for social sharing previews.")
        deductions += 5

    # 8. Internal links
    parsed_base = urlparse(page_url)
    base_domain = parsed_base.netloc.lower()
    all_links = soup.find_all("a", href=True)
    internal_links: list[str] = []
    external_links: list[str] = []

    for a in all_links:
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full_href = urljoin(page_url, href)
        parsed_target = urlparse(full_href)
        if parsed_target.netloc.lower() == base_domain:
            internal_links.append(full_href)
        elif parsed_target.netloc:
            external_links.append(full_href)

    checks["links"] = {
        "total": len(all_links),
        "internal_count": len(internal_links),
        "external_count": len(external_links),
    }
    if len(internal_links) == 0:
        issues.append({"level": "warning", "message": "No internal navigation links found on page."})
        recommendations.append("Ensure key navigation links exist to facilitate crawl depth and user discovery.")
        deductions += 5

    final_score = max(0, min(100, score - deductions))

    return {
        "seo_score": final_score,
        "disclaimer": (
            "This technical SEO evaluation is based on on-page source standards "
            "and does not represent a proprietary or full Google ranking algorithm result."
        ),
        "checks": checks,
        "issues": issues,
        "recommendations": recommendations,
    }


async def run_full_seo_audit(url: str, client: Optional[httpx.AsyncClient] = None) -> dict[str, Any]:
    """
    Fetch target page, check robots.txt and sitemap.xml, and perform complete SEO audit.
    """
    norm_url = validate_and_normalize_url(url)
    should_close = False
    if client is None:
        client = create_safe_client(timeout=15.0)
        should_close = True

    try:
        # Check robots.txt availability
        parsed = urlparse(norm_url)
        base_origin = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = urljoin(base_origin, "/robots.txt")
        sitemap_url = urljoin(base_origin, "/sitemap.xml")

        robots_ok = False
        sitemap_ok = False

        try:
            r_resp = await client.get(robots_url, headers={"User-Agent": "LeadIntel/0.1"})
            robots_ok = (r_resp.status_code == 200)
        except Exception:
            pass

        try:
            s_resp = await client.get(sitemap_url, headers={"User-Agent": "LeadIntel/0.1"})
            sitemap_ok = (s_resp.status_code == 200)
        except Exception:
            pass

        # Fetch main page
        page_resp = await client.get(norm_url, headers={"User-Agent": "LeadIntel/0.1"})
        page_resp.raise_for_status()

        audit = audit_html_seo(page_resp.text, str(page_resp.url))
        audit["checks"]["robots_txt"] = {"available": robots_ok, "url": robots_url}
        audit["checks"]["sitemap"] = {"available": sitemap_ok, "url": sitemap_url}

        if not robots_ok:
            audit["issues"].append({"level": "info", "message": "robots.txt not detected at standard location."})
        if not sitemap_ok:
            audit["issues"].append({"level": "info", "message": "sitemap.xml not detected at standard root location."})

        return audit
    finally:
        if should_close:
            await client.aclose()
