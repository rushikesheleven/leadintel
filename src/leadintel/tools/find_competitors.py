"""
MCP Tool: find_competitors

Discovers relevant industry competitors using OpenStreetMap and semantic taxonomy matching,
classifies them as direct vs indirect, and assesses digital footprints.
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.mcpserver import MCPServer

from ..services.competitor_research import find_industry_competitors


def register(mcp: MCPServer) -> None:
    """Register find_competitors tool on the MCP server."""

    @mcp.tool()
    async def find_competitors(
        business_name: str,
        business_category: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        country: Optional[str] = None,
        website: Optional[str] = None,
        max_competitors: int = 5,
        enrich_websites: bool = True,
    ) -> dict[str, Any]:
        """
        Discover and analyze competitors of a target business.

        Finds industry rivals using OpenStreetMap and semantic taxonomy rules.
        Distinguishes direct competitors (exact specialization overlap) from
        indirect competitors (broader category overlap), explaining confidence levels.

        Features:
        - Filters out unrelated businesses (does not mistake mere geographical proximity for competition).
        - Identifies competitor websites, contact info, ratings, and reviews.
        - Analyzes digital presence (website status, mobile readiness, social media footprint).
        - Zero paid API keys required; respects OpenStreetMap ODbL attribution.

        Args:
            business_name: Name of the target business (e.g. 'Acme Tech Solutions', 'Blue Bottle Coffee').
            business_category: Industry/category of the business (e.g. 'Software Development', 'Cafe').
            city: Optional city (e.g. 'San Francisco', 'London').
            state: Optional state/province (e.g. 'CA', 'TX').
            country: Optional country (e.g. 'US', 'UK').
            website: Optional target company website URL.
            max_competitors: Maximum competitors to return (1-20, default 5).
            enrich_websites: If True, tests competitor websites for availability and digital channels.

        Returns:
            Structured competitor research report.
        """
        limit = max(1, min(int(max_competitors), 20))
        try:
            return await find_industry_competitors(
                business_name=business_name,
                business_category=business_category,
                city=city,
                state=state,
                country=country,
                website=website,
                max_competitors=limit,
                enrich_websites=enrich_websites,
            )
        except Exception as exc:
            return {
                "error": str(exc),
                "target_business": {"name": business_name, "category": business_category},
                "total_competitors_found": 0,
                "competitors": [],
            }
