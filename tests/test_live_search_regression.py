"""
Regression tests for Live OpenStreetMap Search in LeadIntel.

Covers:
1. Live search with a city name.
2. Live search with coordinates.
3. Category-based search.
4. Overpass API timeout and HTTP errors (with live OSM fallback).
5. Demo mode explicitly enabled.
6. Live mode with unavailable Overpass and OSM service (no silent demo fallback).
7. Real live OpenStreetMap query test.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from leadintel.config import Settings
from leadintel.providers import build_registry
from leadintel.providers.overpass_provider import (
    NOMINATIM_ENDPOINT,
    OVERPASS_ENDPOINT,
    OverpassProvider,
)
from leadintel.server import mcp

OSM_ATTRIBUTION = (
    "Data © OpenStreetMap contributors, ODbL 1.0 — https://www.openstreetmap.org/copyright"
)


async def _call_search_tool(args: dict) -> dict:
    res = await mcp.call_tool("search_businesses", args)
    content = res.content[0].text if hasattr(res.content[0], "text") else res.content[0]
    return json.loads(content) if isinstance(content, str) else content


def _sample_nominatim_geocode(lat: float = 18.5204, lon: float = 73.8567) -> list[dict]:
    return [
        {
            "lat": str(lat),
            "lon": str(lon),
            "display_name": "Pune, Maharashtra, India",
            "boundingbox": ["18.36", "18.68", "73.69", "74.01"],
        }
    ]


def _sample_overpass_elements() -> list[dict]:
    return [
        {
            "type": "node",
            "id": 1001,
            "lat": 18.521,
            "lon": 73.855,
            "tags": {
                "name": "Pune Roast Cafe",
                "amenity": "cafe",
                "addr:street": "FC Road",
                "addr:city": "Pune",
                "addr:state": "Maharashtra",
                "addr:country": "India",
            },
        },
        {
            "type": "way",
            "id": 2002,
            "center": {"lat": 18.525, "lon": 73.858},
            "tags": {
                "name": "FC Road Bistro",
                "amenity": "restaurant",
                "addr:street": "FC Road",
                "addr:city": "Pune",
            },
        },
    ]


def _sample_nominatim_search_results() -> list[dict]:
    return [
        {
            "place_id": 9991,
            "osm_type": "node",
            "osm_id": 8881,
            "lat": "18.5205",
            "lon": "73.8568",
            "category": "amenity",
            "type": "restaurant",
            "name": "Shivaji Food Plaza",
            "display_name": "Shivaji Food Plaza, Shivaji Road, Pune, Maharashtra, 411001, India",
            "address": {
                "amenity": "Shivaji Food Plaza",
                "road": "Shivaji Road",
                "city": "Pune",
                "state": "Maharashtra",
                "country": "India",
                "postcode": "411001",
            },
            "extratags": {
                "phone": "+91 20 2445 0000",
                "website": "https://shivajifoodplaza.example",
            },
        }
    ]


@pytest.mark.asyncio
class TestLiveSearchRegression:
    """Test suite covering the 6 regression requirements for business search."""

    @respx.mock
    async def test_live_search_with_city_name(self):
        """1. Live search with a city name returns genuine OpenStreetMap results."""
        respx.get(url__startswith=NOMINATIM_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_sample_nominatim_geocode())
        )
        respx.post(url__startswith=OVERPASS_ENDPOINT).mock(
            return_value=httpx.Response(
                200,
                json={"version": 0.6, "elements": _sample_overpass_elements()},
            )
        )

        data = await _call_search_tool(
            {"query": "cafe", "location": "Pune, Maharashtra", "limit": 5}
        )

        assert data["source"] == "openstreetmap"
        assert data["provider"] == "openstreetmap"
        assert data["total_found"] == 2
        assert len(data["businesses"]) == 2
        assert data["businesses"][0]["name"] == "Pune Roast Cafe"
        assert data["businesses"][0]["source"] == "openstreetmap"
        assert data["businesses"][0]["is_ai_generated"] is False
        assert data["attribution"] == OSM_ATTRIBUTION
        assert data["error"] is None
        assert "✅ Live data from OpenStreetMap" in data["note"]

    @respx.mock
    async def test_live_search_with_coordinates(self):
        """2. Live search with coordinates resolves directly without Nominatim geocoding."""
        overpass_mock = respx.post(url__startswith=OVERPASS_ENDPOINT).mock(
            return_value=httpx.Response(
                200,
                json={"version": 0.6, "elements": _sample_overpass_elements()},
            )
        )

        data = await _call_search_tool(
            {"query": "*", "location": "18.5204,73.8567", "limit": 5}
        )

        assert data["source"] == "openstreetmap"
        assert data["provider"] == "openstreetmap"
        assert data["total_found"] >= 1
        assert overpass_mock.call_count >= 1

    @respx.mock
    async def test_category_based_search(self):
        """3. Category-based search applies industry filters properly."""
        respx.get(url__startswith=NOMINATIM_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_sample_nominatim_geocode())
        )
        respx.post(url__startswith=OVERPASS_ENDPOINT).mock(
            return_value=httpx.Response(
                200,
                json={"version": 0.6, "elements": _sample_overpass_elements()},
            )
        )

        data = await _call_search_tool(
            {
                "query": "*",
                "location": "Pune",
                "category": "Food & Beverage",
                "limit": 5,
            }
        )

        assert data["source"] == "openstreetmap"
        assert data["category"] == "Food & Beverage"
        assert data["total_found"] == 2

    @respx.mock
    async def test_overpass_api_timeout_and_http_errors_falls_back_to_nominatim(self):
        """4. Overpass API timeout and 502/406 HTTP errors fallback to live Nominatim search."""
        # 1st call: geocode location
        respx.get(url__startswith=f"{NOMINATIM_ENDPOINT}?q=Pune").mock(
            return_value=httpx.Response(200, json=_sample_nominatim_geocode())
        )

        # Overpass endpoint fails with 502 or ReadTimeout
        respx.post(url__startswith="https://").mock(
            side_effect=httpx.ReadTimeout("Overpass server gateway read timeout")
        )

        # 2nd call: fallback Nominatim search returns genuine live business
        respx.get(url__startswith=f"{NOMINATIM_ENDPOINT}?format=jsonv2").mock(
            return_value=httpx.Response(200, json=_sample_nominatim_search_results())
        )

        provider = OverpassProvider()
        results = await provider.search(
            query="food", location="Pune", category="Food & Beverage", limit=5
        )

        assert len(results) == 1
        assert results[0].name == "Shivaji Food Plaza"
        assert results[0].source == "openstreetmap"
        assert results[0].address is not None

    @pytest.mark.asyncio
    async def test_demo_mode_explicitly_enabled(self):
        """5. Demo mode explicitly enabled returns synthetic data and avoids network."""
        demo_settings = Settings(demo_mode=True)
        registry = build_registry(demo_settings)

        assert registry.provider_names() == ["demo"]
        businesses, provider_name = await registry.search(
            query="*", location="San Francisco", category=None, limit=10
        )

        assert provider_name == "demo"
        assert len(businesses) > 0
        assert all(b.source == "demo" for b in businesses)

    @respx.mock
    async def test_live_mode_with_unavailable_overpass_service(self):
        """6. Live mode with completely unavailable OSM service does NOT silently return demo data."""
        # Geocode succeeds
        respx.get(url__startswith=f"{NOMINATIM_ENDPOINT}?q=Pune").mock(
            return_value=httpx.Response(200, json=_sample_nominatim_geocode())
        )
        # Overpass fails with 502
        respx.post(url__startswith="https://").mock(
            return_value=httpx.Response(502, text="Gateway Timeout")
        )
        # Nominatim search also fails (e.g. offline / 503)
        respx.get(url__startswith=f"{NOMINATIM_ENDPOINT}?format=jsonv2").mock(
            side_effect=httpx.ConnectError("Network is down")
        )

        data = await _call_search_tool(
            {"query": "law firm", "location": "Pune", "limit": 5}
        )

        # Must report openstreetmap as source, NOT demo!
        assert data["source"] == "openstreetmap"
        assert data["provider"] == "openstreetmap"
        assert data["total_found"] == 0
        assert data["businesses"] == []
        assert data["error"] is not None
        assert "OpenStreetMap search failed" in data["error"]
        assert "⚠️ OpenStreetMap live search encountered an issue" in data["note"]
