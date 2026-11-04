"""Tests for the Business and related Pydantic models."""

from datetime import datetime

import pytest

from leadintel.models.business import Business, BusinessSearchResult, LeadScore
from leadintel.models.report import BusinessReport


class TestBusinessModel:
    def _make_business(self, **kwargs) -> Business:
        defaults = dict(id="test_001", name="Test Corp", source="demo")
        defaults.update(kwargs)
        return Business(**defaults)

    def test_minimal_construction(self):
        biz = self._make_business()
        assert biz.name == "Test Corp"
        assert biz.source == "demo"
        assert biz.is_ai_generated is False

    def test_rating_bounds_valid(self):
        biz = self._make_business(rating=4.9)
        assert biz.rating == 4.9

    def test_rating_too_high_raises(self):
        with pytest.raises(Exception):
            self._make_business(rating=6.0)

    def test_rating_negative_raises(self):
        with pytest.raises(Exception):
            self._make_business(rating=-1.0)

    def test_retrieved_at_defaults_to_now(self):
        before = datetime.utcnow()
        biz = self._make_business()
        after = datetime.utcnow()
        assert before <= biz.retrieved_at <= after

    def test_serialises_to_json(self):
        biz = self._make_business(phone="+1-555-0000", rating=4.5)
        data = biz.model_dump(mode="json")
        assert data["name"] == "Test Corp"
        assert isinstance(data["retrieved_at"], str)

    def test_optional_fields_default_none(self):
        biz = self._make_business()
        for field in ("address", "city", "phone", "email", "website", "linkedin_url"):
            assert getattr(biz, field) is None

    def test_attribution_field_exists(self):
        biz = self._make_business()
        assert biz.attribution is None

    def test_osm_id_property_for_osm_source(self):
        biz = self._make_business(id="osm_node_123456", source="openstreetmap")
        assert biz.osm_id == "osm_node_123456"

    def test_osm_id_property_none_for_demo(self):
        biz = self._make_business(id="demo_001")
        assert biz.osm_id is None

    def test_requires_attribution_for_osm(self):
        biz = self._make_business(id="osm_node_1", source="openstreetmap")
        assert biz.requires_attribution is True

    def test_requires_attribution_false_for_demo(self):
        biz = self._make_business(source="demo")
        assert biz.requires_attribution is False

    def test_osm_record_with_attribution_string(self):
        biz = self._make_business(
            id="osm_way_9999",
            source="openstreetmap",
            attribution="Data © OpenStreetMap contributors, ODbL 1.0",
        )
        assert "OpenStreetMap" in biz.attribution


class TestBusinessSearchResult:
    def test_empty_result(self):
        result = BusinessSearchResult(query="coffee")
        assert result.total_found == 0
        assert result.businesses == []

    def test_with_businesses(self):
        biz = Business(id="x1", name="Foo Inc", source="demo")
        result = BusinessSearchResult(query="foo", total_found=1, businesses=[biz])
        assert result.total_found == 1
        assert result.businesses[0].name == "Foo Inc"

    def test_provider_field_default(self):
        result = BusinessSearchResult(query="test")
        assert result.provider == "demo"

    def test_attribution_field_present(self):
        result = BusinessSearchResult(query="test")
        assert result.attribution is None


class TestLeadScore:
    def test_valid_score(self):
        ls = LeadScore(
            business_id="x1",
            business_name="Foo Inc",
            score=72.5,
            grade="B",
        )
        assert ls.grade == "B"
        assert ls.score == 72.5

    def test_score_out_of_range(self):
        with pytest.raises(Exception):
            LeadScore(business_id="x1", business_name="Foo", score=101, grade="A")

    def test_scored_at_serialises(self):
        ls = LeadScore(business_id="x", business_name="Y", score=50, grade="C")
        data = ls.model_dump(mode="json")
        assert isinstance(data["scored_at"], str)


class TestBusinessReport:
    def test_default_disclaimer(self):
        biz = Business(id="r1", name="Report Co", source="demo")
        report = BusinessReport(business=biz)
        assert "Verify" in report.disclaimer

    def test_is_not_ai_generated_by_default(self):
        biz = Business(id="r1", name="Report Co", source="demo")
        report = BusinessReport(business=biz)
        assert report.is_ai_generated is False
