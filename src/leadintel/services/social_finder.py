"""
Social Media Profile Finder Service.

Extracts official social media links from HTML documents and handles
filtering of share buttons, tracking parameters, and unrelated external links.
"""

from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Canonical platform regexes
_PLATFORMS: dict[str, list[re.Pattern]] = {
    "linkedin": [
        re.compile(r"^https?://(www\.)?linkedin\.com/(company|in|school)/[a-zA-Z0-9_\-\.]+/?", re.IGNORECASE)
    ],
    "facebook": [
        re.compile(r"^https?://(www\.)?facebook\.com/[a-zA-Z0-9_\-\.]+/?", re.IGNORECASE)
    ],
    "instagram": [
        re.compile(r"^https?://(www\.)?instagram\.com/[a-zA-Z0-9_\-\.]+/?", re.IGNORECASE)
    ],
    "twitter": [
        re.compile(r"^https?://(www\.)?(twitter|x)\.com/[a-zA-Z0-9_]{1,30}/?", re.IGNORECASE)
    ],
    "youtube": [
        re.compile(r"^https?://(www\.)?youtube\.com/(@[a-zA-Z0-9_\-\.]+|channel/[a-zA-Z0-9_\-]+|c/[a-zA-Z0-9_\-]+)/?", re.IGNORECASE)
    ],
    "pinterest": [
        re.compile(r"^https?://(www\.)?pinterest\.(com|[a-z]{2})/[a-zA-Z0-9_\-\.]+/?", re.IGNORECASE)
    ],
}

# Paths/query parameters indicating sharing intent rather than profile links
_IGNORE_PATTERNS = [
    re.compile(r"sharer|share\.php|intent/tweet|sharing|dialog/share|pin/create", re.IGNORECASE),
    re.compile(r"linkedin\.com/shareArticle", re.IGNORECASE),
]


def _clean_social_url(url: str) -> Optional[str]:
    """Clean query parameters and check if URL is a profile vs sharing link."""
    for pattern in _IGNORE_PATTERNS:
        if pattern.search(url):
            return None

    try:
        parsed = urlparse(url)
        # Strip tracking query params
        path = parsed.path.rstrip("/")
        if not path or path in ("", "/"):
            return None

        # Exclude common non-profile paths
        ignored_paths = {
            "/login", "/signup", "/home", "/privacy", "/terms", "/help",
            "/about", "/policies", "/share", "/tr", "/plugins"
        }
        if path.lower() in ignored_paths:
            return None

        clean_url = urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", "", ""))
        return clean_url
    except Exception:
        return None


def extract_social_profiles(html_content: str, base_url: str = "") -> dict[str, list[dict[str, str]]]:
    """
    Extract verified social media profiles from HTML content.

    Returns dict mapping platform name to list of dicts:
    {
      "linkedin": [{"url": "https://linkedin.com/company/acme", "source_page": base_url}],
      ...
    }
    """
    results: dict[str, list[dict[str, str]]] = {p: [] for p in _PLATFORMS}
    seen_urls: set[str] = set()

    if not html_content:
        return results

    try:
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception as e:
        logger.debug("HTML parsing failed in extract_social_profiles: %s", e)
        return results

    links = soup.find_all("a", href=True)
    for a in links:
        href = a["href"].strip()
        if not href.startswith("http"):
            continue

        for platform, patterns in _PLATFORMS.items():
            matched = False
            for pat in patterns:
                if pat.search(href):
                    cleaned = _clean_social_url(href)
                    if cleaned and cleaned not in seen_urls:
                        seen_urls.add(cleaned)
                        results[platform].append({
                            "url": cleaned,
                            "source_page": base_url or "",
                        })
                    matched = True
                    break
            if matched:
                break

    return results
