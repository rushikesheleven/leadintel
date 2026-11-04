"""Tests for get_business_details and find_business_website tools."""

from __future__ import annotations

import httpx
import pytest
import respx

from leadintel.providers.overpass_provider import OVERPASS_ENDPOINT
from leadintel.server import mcp
from leadintel.tools.website_finder import find_website_for_business


@pytest.mark.asyncio
class TestGetBusinessDetails:
    async def test_get_demo_business_details_found(self):
        result = await mcp.call_tool("get_business_details", {"business_id": "demo_001"})
        data = result.content[0].text if hasattr(result.content[0], "text") else result.content[0]
        import json
        payload = json.loads(data) if isinstance(data, str) else data

        assert payload["found"] is True
        assert payload["business_id"] == "demo_001"
        assert payload["business"]["name"] == "Acme Tech Solutions"
        assert payload["business"]["website"] == "https://acmetech.example"
        assert payload["provider"] == "demo"

    async def test_get_business_details_not_found(self):
        result = await mcp.call_tool("get_business_details", {"business_id": "nonexistent_999"})
        data = result.content[0].text if hasattr(result.content[0], "text") else result.content[0]
        import json
        payload = json.loads(data) if isinstance(data, str) else data

        assert payload["found"] is False
        assert payload["business"] is None

    @respx.mock
    async def test_get_osm_business_details_with_auto_enrich(self):
        # Mock Overpass node lookup returning element without website
        element = {
            "type": "node",
            "id": 8888,
            "lat": 37.7749,
            "lon": -122.4194,
            "tags": {
                "name": "Acme Tech Solutions",
                "addr:city": "San Francisco",
                "amenity": "cafe",
            },
        }
        respx.post(OVERPASS_ENDPOINT).mock(
            return_value=httpx.Response(200, json={"elements": [element]})
        )

        result = await mcp.call_tool("get_business_details", {"business_id": "osm_node_8888", "auto_enrich_website": True})
        import json
        data = result.content[0].text if hasattr(result.content[0], "text") else result.content[0]
        payload = json.loads(data) if isinstance(data, str) else data

        assert payload["found"] is True
        assert payload["business"]["name"] == "Acme Tech Solutions"
        assert payload["attribution"] is not None
        assert "OpenStreetMap" in payload["attribution"]


@pytest.mark.asyncio
class TestFindBusinessWebsite:
    async def test_find_website_for_demo_id(self):
        url, method = await find_website_for_business("Acme Tech Solutions", business_id="demo_001")
        assert url == "https://acmetech.example"
        assert "provider" in method or "demo" in method

    async def test_find_website_demo_fallback_by_name(self):
        url, method = await find_website_for_business("GreenLeaf Consulting")
        assert url == "https://greenleafconsulting.example"

    @respx.mock
    async def test_find_website_duckduckgo_lite(self):
        # Mock duckduckgo html search
        ddg_html = """
        <html><body>
        <div class="results">
            <a class="result__url" href="/l/?uddg=https%3A%2F%2Findependent-cafe-london.co.uk%2Fabout">independent-cafe-london.co.uk</a>
        </div>
        </body></html>
        """
        respx.get(url__startswith="https://html.duckduckgo.com/html/").mock(
            return_value=httpx.Response(200, text=ddg_html)
        )

        url, method = await find_website_for_business("Independent Cafe London", location="London")
        assert url == "https://independent-cafe-london.co.uk/about"
        assert method == "duckduckgo_lite"

    async def test_mcp_find_business_website_tool_execution(self):
        result = await mcp.call_tool("find_business_website", {
            "business_name": "Acme Tech Solutions",
            "business_id": "demo_001"
        })
        import json
        data = result.content[0].text if hasattr(result.content[0], "text") else result.content[0]
        payload = json.loads(data) if isinstance(data, str) else data

        assert payload["found"] is True
        assert payload["website"] == "https://acmetech.example"
        assert payload["business_name"] == "Acme Tech Solutions"

    async def test_find_business_website_empty_query(self):
        url, method = await find_website_for_business("", location="")
        assert url is None
        assert method == "empty_query"
