"""
MCP Tool: find_business_website

Discovers and validates the official website of a business entity.
Uses OpenStreetMap data first, followed by free web search lookup and validation.
"""

from __future__ import annotations

from typing import Optional

from mcp.server.mcpserver import MCPServer

from .website_finder import find_website_for_business


def register(mcp: MCPServer) -> None:
    """Register find_business_website tool on the MCP server."""

    @mcp.tool()
    async def find_business_website(
        business_name: str,
        location: Optional[str] = None,
        business_id: Optional[str] = None,
    ) -> dict:
        """
        Find and verify the official website of a business.

        Searches local knowledge providers and free web search (no paid API key required).
        Filters out directories, social media links, and aggregators to isolate the primary domain.

        Args:
            business_name: Name of the business (e.g. 'Blue Bottle Coffee', 'Acme Corp').
            location: Optional location context (e.g. 'San Francisco', 'London').
            business_id: Optional unique LeadIntel/OSM ID (e.g. 'osm_node_123', 'demo_001').

        Returns:
            Dict containing:
              - found (bool): True if an official website was identified
              - business_name (str): Input business name
              - location (str|null): Input location
              - website (str|null): Discovered website URL
              - discovery_method (str): Method used ('provider:openstreetmap', 'duckduckgo_lite', etc.)
              - note (str|null): Informative status note
        """
        website_url, method = await find_website_for_business(
            business_name=business_name,
            location=location,
            business_id=business_id,
        )

        found = bool(website_url)

        return {
            "found": found,
            "business_name": business_name,
            "location": location,
            "business_id": business_id,
            "website": website_url,
            "discovery_method": method,
            "note": (
                f"Discovered website via {method}."
                if found
                else "Could not locate a verified official website."
            ),
        }
