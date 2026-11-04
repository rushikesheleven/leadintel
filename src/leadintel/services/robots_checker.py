"""
Robots.txt Parser & Checker Service.

Checks robots.txt policies using standard python urllib.robotparser,
with respectful timeouts, caching, and User-Agent matching.
"""

from __future__ import annotations

import logging
import urllib.robotparser
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

from .url_validator import SecurityValidationError, create_safe_client, validate_and_normalize_url

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "LeadIntel/0.1 (Business Intelligence Researcher; +https://github.com/example/leadintel; respectful crawler)"
_ROBOTS_CACHE: dict[str, tuple[float, urllib.robotparser.RobotFileParser]] = {}


class RobotsChecker:
    """Manages fetching, parsing, and caching robots.txt for websites."""

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT, timeout: float = 10.0):
        self.user_agent = user_agent
        self.timeout = timeout

    async def can_fetch(self, target_url: str, client: Optional[httpx.AsyncClient] = None) -> tuple[bool, Optional[str]]:
        """
        Check if target_url can be crawled according to the site's robots.txt.

        Returns:
            (allowed: bool, reason_or_robots_url: Optional[str])
        """
        try:
            norm_url = validate_and_normalize_url(target_url)
        except SecurityValidationError as e:
            return False, f"Blocked by URL security validation: {e}"
        except Exception as e:
            return False, f"Invalid URL: {e}"

        parsed = urlparse(norm_url)
        base_origin = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = urljoin(base_origin, "/robots.txt")

        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)

        try:
            should_close = False
            if client is None:
                client = create_safe_client(timeout=self.timeout)
                should_close = True

            try:
                resp = await client.get(robots_url, headers={"User-Agent": self.user_agent})
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                elif resp.status_code in (401, 403):
                    # Access denied to robots.txt usually implies entire site is disallowed or restricted
                    return False, f"robots.txt returned HTTP {resp.status_code}"
                else:
                    # 404 or other errors typically mean crawling is allowed per RFC standards
                    return True, None
            finally:
                if should_close:
                    await client.aclose()

            allowed = rp.can_fetch(self.user_agent, norm_url)
            if not allowed:
                return False, f"Disallowed by rules in {robots_url}"
            return True, None

        except Exception as e:
            logger.debug("Failed to check robots.txt for %s: %s", robots_url, e)
            # Default to allowed on fetch errors (unless server actively blocked with 401/403)
            return True, None
