"""
MCP Tool: compare_businesses

Benchmark a target business against one or more competitors, generating
a side-by-side comparison matrix, strengths, weaknesses, and digital opportunities.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..services.business_comparison import compare_target_against_competitors


def register(mcp: MCPServer) -> None:
    """Register compare_businesses tool on the MCP server."""

    @mcp.tool()
    async def compare_businesses(
        target_business: dict[str, Any],
        competitor_businesses: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Compare a target business against a list of competitor businesses.

        Benchmarks organizations across critical digital and operational dimensions:
        - Website availability & response time
        - Technical SEO score (0-100)
        - HTTPS/SSL security configuration
        - Mobile viewport readiness
        - Social media footprint (channels active)
        - Contact accessibility (forms, direct email, direct phone)
        - Public reviews and ratings where available

        Outputs:
        - Structured comparison table matrix
        - High-confidence strengths
        - Critical digital weaknesses
        - High-leverage growth opportunities
        - Executive competitive positioning summary

        Args:
            target_business: Dict representing target company. Must include 'name', optional 'website', 'category', 'city'.
            competitor_businesses: List of dicts representing competitor companies to benchmark against.

        Returns:
            Comprehensive competitive intelligence comparison report.
        """
        try:
            return await compare_target_against_competitors(
                target_business=target_business,
                competitors=competitor_businesses,
            )
        except Exception as exc:
            return {
                "error": str(exc),
                "target_business": target_business.get("name") if isinstance(target_business, dict) else str(target_business),
                "comparison_matrix": [],
                "strengths": [],
                "weaknesses": [],
                "opportunities": [],
                "competitive_positioning_summary": f"Comparison failed: {exc}",
            }
