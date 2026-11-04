"""
MCP Tool: check_seo

Custom, free Python SEO audit tool evaluating on-page metadata,
headings, robots.txt, sitemaps, open graph, and link architecture.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..services.seo_auditor import run_full_seo_audit


def register(mcp: MCPServer) -> None:
    """Register check_seo tool on the MCP server."""

    @mcp.tool()
    async def check_seo(
        url: str,
    ) -> dict[str, Any]:
        """
        Run a technical on-page SEO audit on a business website.

        Evaluates fundamental search engine optimization signals:
        - Missing or duplicate title tags and length bounds.
        - Missing or suboptimal meta descriptions.
        - Missing H1 or multiple H1 heading tags.
        - Missing image alt attributes and overall image alt coverage percentage.
        - Canonical URL link specification.
        - Meta robots directives (noindex/nofollow).
        - Availability of robots.txt and sitemap.xml.
        - Open Graph tags for social preview readiness.
        - Internal link count and page weight.

        Output:
        - SEO score from 0 to 100.
        - Detailed checklist breakdown.
        - Specific prioritized issues (errors, warnings, info).
        - Actionable recommendations.

        Notice:
        This is an on-page technical SEO diagnostic tool and not an official
        Google ranking assessment or proprietary PageRank score.

        Args:
            url: The target website URL (e.g. 'https://example.com').

        Returns:
            Structured SEO audit report.
        """
        try:
            return await run_full_seo_audit(url=url)
        except Exception as exc:
            return {
                "seo_score": 0,
                "url": url,
                "error": str(exc),
                "disclaimer": "This technical audit requires a reachable, valid website URL.",
                "issues": [{"level": "error", "message": f"Could not perform audit: {exc}"}],
                "recommendations": ["Verify website is publicly accessible and URL is correct."],
            }
