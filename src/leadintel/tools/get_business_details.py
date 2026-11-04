"""
MCP Tool: get_business_details

Fetches complete and enriched information for a single business entity,
using OpenStreetMap / Overpass data, local demo fallback, and website resolution.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from ..config import settings
from ..models.business import Business
from ..providers import build_registry
from .website_finder import find_website_for_business

OSM_ATTRIBUTION = "Data © OpenStreetMap contributors, ODbL 1.0 — https://www.openstreetmap.org/copyright"

_registry = build_registry(settings)


def register(mcp: MCPServer) -> None:
    """Register get_business_details tool on the MCP server."""

    @mcp.tool()
    async def get_business_details(
        business_id: str,
        auto_enrich_website: bool = True,
    ) -> dict:
        """
        Retrieve enriched details for a specific business by ID.

        Looks up the entity across all available providers (OpenStreetMap, demo fixtures).
        If the business is missing a website and `auto_enrich_website` is True,
        attempts to discover its official website.

        Args:
            business_id: Unique identifier (e.g. 'osm_node_12345', 'osm_way_67890', or 'demo_001').
            auto_enrich_website: If True, search for missing official website if not present in OSM tags.

        Returns:
            Dict containing:
              - found (bool): Whether the business was resolved
              - business (dict|null): Enriched business record
              - provider (str): Source of the data
              - attribution (str|null): Mandatory attribution notice if source is OSM
              - enriched_fields (list[str]): Fields added or updated via enrichment

        Compliance:
            - Respects OSM ODbL attribution.
            - Does not scrape private personal information.
        """
        enriched_fields: list[str] = []

        biz, provider_name = await _registry.get_details(business_id)

        if not biz:
            return {
                "found": False,
                "business_id": business_id,
                "business": None,
                "provider": provider_name,
                "attribution": None,
                "enriched_fields": [],
                "note": f"Business ID '{business_id}' not found.",
            }

        # Auto-enrich website if absent
        if auto_enrich_website and not biz.website and biz.name:
            discovered_url, _ = await find_website_for_business(
                business_name=biz.name,
                location=biz.city,
                business_id=biz.id,
            )
            if discovered_url:
                # Update website field
                biz_dict = biz.model_dump()
                biz_dict["website"] = discovered_url
                biz = Business(**biz_dict)
                enriched_fields.append("website")

        is_osm = provider_name == "openstreetmap" or biz.source == "openstreetmap"
        attribution = OSM_ATTRIBUTION if is_osm else None

        return {
            "found": True,
            "business_id": business_id,
            "business": biz.model_dump(mode="json"),
            "provider": provider_name,
            "attribution": attribution,
            "enriched_fields": enriched_fields,
            "note": (
                "Enriched via LeadIntel free intelligence. "
                + (f"Attribution: {OSM_ATTRIBUTION}" if is_osm else "")
            ).strip(),
        }
