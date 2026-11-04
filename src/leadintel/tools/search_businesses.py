"""MCP tool: search_businesses — powered by the provider registry."""

from __future__ import annotations

from typing import Optional

from mcp.server.mcpserver import MCPServer

from ..config import settings
from ..models.business import BusinessSearchResult
from ..providers import build_registry

OSM_ATTRIBUTION = "Data © OpenStreetMap contributors, ODbL 1.0 — https://www.openstreetmap.org/copyright"

_registry = build_registry(settings)


def register(mcp: MCPServer) -> None:
    """Register search_businesses tool on the MCP server."""

    @mcp.tool()
    async def search_businesses(
        query: str,
        location: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> dict:
        """
        Search for businesses matching a query using free, open data sources.

        Uses OpenStreetMap / Overpass API for live discovery (no API key required).
        Falls back to demo data when the network is unavailable or DEMO_MODE=true.

        Args:
            query:    Free-text search term, e.g. "coffee shop", "software company",
                      "law firm", "restaurant". Pass "*" for a broad sweep.
            location: City, region, or "lat,lon" coordinates to centre the search,
                      e.g. "London", "Austin, TX", "48.8566,2.3522".
                      Required for live OSM search — omitting it falls back to demo data.
            category: Optional industry hint, e.g. "Technology", "Healthcare",
                      "Food & Beverage". Narrows the Overpass tag filter.
            limit:    Maximum results to return (1–50, default 10).

        Returns:
            dict with keys:
              query, location, category  — echoed inputs
              total_found (int)          — number of matching results
              businesses (list[dict])    — business records
              provider (str)             — data source used
              retrieved_at (str)         — ISO-8601 timestamp
              attribution (str|null)     — ODbL attribution (show this when displaying OSM data)
              note (str|null)            — caveat about data quality or mode

        Attribution:
            When provider is "openstreetmap", you MUST display the attribution string
            "Data © OpenStreetMap contributors, ODbL 1.0" wherever results appear.

        Compliance:
            - OpenStreetMap data is used under the ODbL licence.
            - No data is sent to third parties.
            - is_ai_generated=False for all records from this tool.
        """
        limit = max(1, min(limit, 50))

        businesses, provider_name = await _registry.search(
            query=query,
            location=location,
            category=category,
            limit=limit,
        )

        is_osm = provider_name == "openstreetmap"
        is_demo = provider_name == "demo"

        note: Optional[str] = None
        if is_demo:
            note = (
                "ℹ️ Demo data returned. "
                "Provide a 'location' parameter to enable live OpenStreetMap search "
                "(no API key required)."
            )
        elif is_osm:
            note = (
                f"✅ Live data from OpenStreetMap. "
                f"Attribution required: {OSM_ATTRIBUTION}"
            )

        result = BusinessSearchResult(
            query=query,
            location=location,
            category=category,
            total_found=len(businesses),
            businesses=businesses,
            source=provider_name,
            provider=provider_name,
            attribution=OSM_ATTRIBUTION if is_osm else None,
            note=note,
        )

        return result.model_dump(mode="json")
