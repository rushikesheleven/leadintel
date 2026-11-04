"""Tests for the DemoProvider."""

import pytest

from leadintel.models.business import Business
from leadintel.providers.demo_provider import DemoProvider


class TestDemoProvider:
    def test_name(self):
        assert DemoProvider.name == "demo"

    def test_requires_auth_false(self):
        assert DemoProvider.requires_auth is False


@pytest.mark.asyncio
class TestDemoProviderAsync:
    async def test_search_wildcard_returns_all(self):
        p = DemoProvider()
        results = await p.search("*", None, None, 100)
        assert len(results) > 0
        assert all(isinstance(b, Business) for b in results)

    async def test_search_with_location_filter(self):
        p = DemoProvider()
        results = await p.search("*", "San Francisco", None, 10)
        assert all(b.city == "San Francisco" for b in results)

    async def test_search_empty_query_returns_all(self):
        p = DemoProvider()
        results = await p.search("", None, None, 100)
        assert len(results) > 0

    async def test_search_limit_respected(self):
        p = DemoProvider()
        results = await p.search("*", None, None, 1)
        assert len(results) <= 1

    async def test_search_no_match_returns_empty(self):
        p = DemoProvider()
        results = await p.search("zzznomatch_xyx", None, None, 10)
        assert results == []

    async def test_get_details_valid_id(self):
        p = DemoProvider()
        biz = await p.get_details("demo_001")
        assert biz is not None
        assert biz.name == "Acme Tech Solutions"

    async def test_get_details_invalid_id(self):
        p = DemoProvider()
        result = await p.get_details("does_not_exist")
        assert result is None

    async def test_all_results_have_required_fields(self):
        p = DemoProvider()
        results = await p.search("*", None, None, 100)
        for biz in results:
            assert biz.id
            assert biz.name
            assert biz.source == "demo"
            assert biz.is_ai_generated is False
