"""Tests for the search_businesses MCP tool logic."""

import pytest

from leadintel.data.demo import DEMO_BUSINESSES, search_demo_businesses
from leadintel.models.business import BusinessSearchResult


class TestSearchBusinessesLogic:
    """Tests for the search / filter logic underlying the MCP tool."""

    def test_search_returns_correct_type(self):
        results = search_demo_businesses(query="tech")
        assert isinstance(results, list)
        for biz in results:
            from leadintel.models.business import Business
            assert isinstance(biz, Business)

    def test_search_limit_50(self):
        # Even with 200 limit, demo dataset caps naturally
        results = search_demo_businesses(query="*", limit=200)
        assert len(results) <= len(DEMO_BUSINESSES)

    def test_search_result_model_roundtrip(self):
        businesses = search_demo_businesses(query="*")
        result = BusinessSearchResult(
            query="*",
            total_found=len(businesses),
            businesses=businesses,
            source="demo",
        )
        data = result.model_dump(mode="json")
        assert data["source"] == "demo"
        assert len(data["businesses"]) == len(businesses)

    def test_all_results_have_required_fields(self):
        results = search_demo_businesses(query="*")
        for biz in results:
            assert biz.id
            assert biz.name
            assert biz.source

    def test_no_secrets_in_results(self):
        """Sanity check: results should never contain API keys."""
        results = search_demo_businesses(query="*")
        for biz in results:
            data = biz.model_dump(mode="json")
            for v in data.values():
                if isinstance(v, str):
                    assert "api_key" not in v.lower()
                    assert "secret" not in v.lower()


@pytest.mark.asyncio
async def test_search_businesses_tool_fatal_error_handling(monkeypatch: pytest.MonkeyPatch):
    """Verify fatal unexpected exceptions return structured error without crashing MCP."""
    import json

    import leadintel.tools.search_businesses as sb_tool
    from leadintel.server import mcp

    # Force an unexpected exception during registry search
    def mock_broken_search(*args, **kwargs):
        raise RuntimeError("Simulated network kernel panic")

    monkeypatch.setattr(sb_tool._registry, "search", mock_broken_search)

    res = await mcp.call_tool("search_businesses", {"query": "fail", "location": "ErrorCity"})
    content = res.content[0].text if hasattr(res.content[0], "text") else str(res.content[0])
    parsed = json.loads(content)

    assert parsed["query"] == "fail"
    assert parsed["location"] == "ErrorCity"
    assert "Internal execution error" in parsed["error"]
    assert "Simulated network kernel panic" in parsed["error"]
    assert parsed["total_found"] == 0
    assert parsed["businesses"] == []

