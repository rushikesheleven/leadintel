"""Tests for demo data layer."""

from leadintel.data.demo import DEMO_BUSINESSES, get_demo_business, search_demo_businesses


class TestSearchDemoBusinesses:
    def test_wildcard_returns_all(self):
        results = search_demo_businesses(query="*")
        assert len(results) == len(DEMO_BUSINESSES)

    def test_empty_query_returns_all(self):
        results = search_demo_businesses(query="")
        assert len(results) == len(DEMO_BUSINESSES)

    def test_query_by_name_partial(self):
        results = search_demo_businesses(query="acme")
        assert any("Acme" in b.name for b in results)

    def test_query_by_category(self):
        results = search_demo_businesses(query="digital")
        assert any("Digital" in (b.category or "") for b in results)

    def test_location_filter(self):
        results = search_demo_businesses(query="*", location="New York")
        assert all(b.city == "New York" for b in results)

    def test_category_filter(self):
        results = search_demo_businesses(query="*", category="Cloud")
        assert all("Cloud" in (b.category or "") for b in results)

    def test_limit_respected(self):
        results = search_demo_businesses(query="*", limit=2)
        assert len(results) <= 2

    def test_no_match_returns_empty(self):
        results = search_demo_businesses(query="zzznomatch", location=None, category=None)
        assert results == []

    def test_source_field_is_demo(self):
        results = search_demo_businesses(query="*")
        assert all(b.source == "demo" for b in results)


class TestGetDemoBusinesses:
    def test_get_by_valid_id(self):
        biz = get_demo_business("demo_001")
        assert biz is not None
        assert biz.name == "Acme Tech Solutions"

    def test_get_by_invalid_id_returns_none(self):
        biz = get_demo_business("nonexistent_id")
        assert biz is None

    def test_all_demo_ids_resolvable(self):
        for biz in DEMO_BUSINESSES:
            found = get_demo_business(biz.id)
            assert found is not None
            assert found.id == biz.id
