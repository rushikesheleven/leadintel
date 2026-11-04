"""
MCP Tool: analyze_website

Comprehensive diagnostic tool for evaluating website availability,
mobile readiness, HTML structure, contact channels, and broken internal links.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..services.website_analyzer import analyze_target_website


def register(mcp: MCPServer) -> None:
    """Register analyze_website tool on the MCP server."""

    @mcp.tool()
    async def analyze_website(
        url: str,
        check_broken_links: bool = True,
    ) -> dict[str, Any]:
        """
        Analyze a business website for technical readiness, structure, and contacts.

        Performs non-invasive examination of the target website:
        - HTTP/HTTPS status and SSL verification.
        - Title, meta description, and mobile viewport configuration.
        - H1/H2 heading hierarchy and image alt tag presence.
        - Public email addresses, telephone numbers, and contact forms.
        - Linked social media profiles.
        - Sampled check for broken internal links.

        Security & Compliance:
        - Respects robots.txt directives before scraping.
        - Protects against SSRF (blocks localhost, private networks, cloud metadata).
        - Enforces request timeouts and max page size limits.
        - Does not scrape private or sensitive personal info.

        Args:
            url: The target website URL (e.g. 'https://example.com').
            check_broken_links: If True, spot-checks up to 10 internal links for broken status (default: True).

        Returns:
            Structured diagnostic dictionary.
        """
        try:
            return await analyze_target_website(url=url, check_broken_links=check_broken_links)
        except Exception as exc:
            return {
                "status": "error",
                "url": url,
                "available": False,
                "error": str(exc),
            }
