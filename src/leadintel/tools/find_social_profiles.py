"""
MCP Tool: find_social_profiles

Scans a company's website to extract and verify official social media profiles.
"""

from __future__ import annotations

from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

from ..services.robots_checker import RobotsChecker
from ..services.social_finder import extract_social_profiles
from ..services.url_validator import validate_and_normalize_url

USER_AGENT = "LeadIntel/0.1 (Business Intelligence Researcher; +https://github.com/example/leadintel; respectful crawler)"


def register(mcp: MCPServer) -> None:
    """Register find_social_profiles tool on the MCP server."""

    @mcp.tool()
    async def find_social_profiles(
        url: str,
    ) -> dict[str, Any]:
        """
        Extract verified official social media profiles from a business website.

        Discovers:
        - LinkedIn (company / personal)
        - Facebook
        - Instagram
        - Twitter / X
        - YouTube
        - Pinterest

        Filters out share/dialog widgets, intent links, and irrelevant external domains.

        Security & Privacy:
        - Prevents SSRF attacks.
        - Respects robots.txt rules.
        - Only extracts publicly linked B2B / official brand profiles.

        Args:
            url: The business website URL (e.g. 'https://acme.example').

        Returns:
            Dict containing detected profiles by platform and total count.
        """
        try:
            norm_url = validate_and_normalize_url(url)
            robots = RobotsChecker()
            can_fetch, reason = await robots.can_fetch(norm_url)
            if not can_fetch:
                return {
                    "url": norm_url,
                    "status": "blocked_by_robots",
                    "error": reason or "Blocked by website robots.txt policy.",
                    "profiles": {},
                    "total_profiles_found": 0,
                }

            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(norm_url, headers={"User-Agent": USER_AGENT})
                resp.raise_for_status()

            profiles = extract_social_profiles(resp.text, base_url=str(resp.url))
            total_found = sum(len(items) for items in profiles.values())

            return {
                "url": str(resp.url),
                "status": "success",
                "profiles": profiles,
                "total_profiles_found": total_found,
            }
        except Exception as exc:
            return {
                "url": url,
                "status": "error",
                "error": str(exc),
                "profiles": {},
                "total_profiles_found": 0,
            }
