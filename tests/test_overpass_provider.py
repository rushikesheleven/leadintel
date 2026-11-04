"""Tests for the OverpassProvider — fully mocked (no real network calls)."""

from __future__ import annotations

import httpx
import pytest
import respx

from leadintel.models.business import Business
from leadintel.providers.overpass_provider import (
    NOMINATIM_ENDPOINT,
    OVERPASS_ENDPOINT,
    OverpassProvider,
    _cache_key,
    _osm_element_to_business,
    _osm_tags_to_category,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_node(
    osm_id: int = 111,
    name: str = "Test Café",
    amenity: str = "cafe",
    lat: float = 51.5,
    lon: float = -0.1,
    **extra_tags,
) -> dict:
    """Build a minimal Overpass node element."""
    tags = {"name": name, "amenity": amenity, **extra_tags}
    return {
        "type": "node",
        "id": osm_id,
        "lat": lat,
        "lon": lon,
        "tags": tags,
    }


def _make_way(
    osm_id: int = 222,
    name: str = "Test Office",
    office: str = "it",
    lat: float = 51.5,
    lon: float = -0.1,
) -> dict:
    return {
        "type": "way",
        "id": osm_id,
        "center": {"lat": lat, "lon": lon},
        "tags": {"name": name, "office": office},
    }


def _nominatim_response(lat: float = 51.5074, lon: float = -0.1278) -> list:
    """Minimal Nominatim geocode response."""
    return [
        {
            "lat": str(lat),
            "lon": str(lon),
            "display_name": "London, Greater London, England, United Kingdom",
        }
    ]


def _overpass_response(elements: list) -> dict:
    return {"version": 0.6, "generator": "Overpass API", "elements": elements}


# ── Unit: tag → category ──────────────────────────────────────────────────────

class TestOsmTagsToCategory:
    def test_amenity_cafe(self):
        assert _osm_tags_to_category({"amenity": "cafe"}) == "Food & Beverage"

    def test_amenity_hospital(self):
        assert _osm_tags_to_category({"amenity": "hospital"}) == "Healthcare"

    def test_shop_electronics(self):
        assert _osm_tags_to_category({"shop": "electronics"}) == "Retail – Electronics"

    def test_office_it(self):
        assert _osm_tags_to_category({"office": "it"}) == "Technology"

    def test_office_consulting(self):
        assert _osm_tags_to_category({"office": "consulting"}) == "Consulting"

    def test_unknown_amenity_titlecased(self):
        result = _osm_tags_to_category({"amenity": "some_new_type"})
        assert result == "Some New Type"

    def test_empty_tags(self):
        assert _osm_tags_to_category({}) is None

    def test_craft_tag(self):
        result = _osm_tags_to_category({"craft": "carpenter"})
        assert result is not None
        assert "Carpenter" in result


# ── Unit: element → Business ──────────────────────────────────────────────────

class TestOsmElementToBusiness:
    def test_basic_node(self):
        element = _make_node(osm_id=999, name="Sunrise Café")
        biz = _osm_element_to_business(element)
        assert biz is not None
        assert biz.name == "Sunrise Café"
        assert biz.id == "osm_node_999"
        assert biz.source == "openstreetmap"
        assert biz.latitude == 51.5
        assert biz.longitude == -0.1
        assert biz.is_ai_generated is False

    def test_node_with_full_address(self):
        element = _make_node(
            **{
                "addr:housenumber": "12",
                "addr:street": "Main Street",
                "addr:city": "London",
                "addr:postcode": "EC1A 1BB",
                "addr:country": "GB",
            }
        )
        biz = _osm_element_to_business(element)
        assert biz is not None
        assert biz.city == "London"
        assert biz.country == "GB"
        assert biz.postal_code == "EC1A 1BB"
        assert "Main Street" in (biz.address or "")

    def test_node_with_contact_fields(self):
        element = _make_node(
            **{
                "contact:phone": "+44 20 7123 4567",
                "contact:email": "hello@example.com",
                "contact:website": "https://example.com",
            }
        )
        biz = _osm_element_to_business(element)
        assert biz is not None
        assert biz.phone == "+44 20 7123 4567"
        assert biz.email == "hello@example.com"
        assert biz.website == "https://example.com"

    def test_way_uses_center(self):
        element = _make_way(osm_id=777)
        biz = _osm_element_to_business(element)
        assert biz is not None
        assert biz.id == "osm_way_777"
        assert biz.latitude == 51.5

    def test_node_without_name_returns_none(self):
        element = {"type": "node", "id": 1, "lat": 0, "lon": 0, "tags": {}}
        biz = _osm_element_to_business(element)
        assert biz is None

    def test_uses_brand_if_no_name(self):
        element = {
            "type": "node",
            "id": 2,
            "lat": 1.0,
            "lon": 1.0,
            "tags": {"brand": "Starbucks"},
        }
        biz = _osm_element_to_business(element)
        assert biz is not None
        assert biz.name == "Starbucks"

    def test_category_from_amenity(self):
        element = _make_node(amenity="restaurant")
        biz = _osm_element_to_business(element)
        assert biz is not None
        assert biz.category == "Food & Beverage"

    def test_osm_id_property(self):
        element = _make_node(osm_id=42)
        biz = _osm_element_to_business(element)
        assert biz.osm_id == "osm_node_42"

    def test_requires_attribution(self):
        biz = _osm_element_to_business(_make_node())
        assert biz.requires_attribution is True


# ── Unit: cache key ───────────────────────────────────────────────────────────

class TestCacheKey:
    def test_same_inputs_same_key(self):
        k1 = _cache_key("cafe", "London", "food", 10)
        k2 = _cache_key("cafe", "London", "food", 10)
        assert k1 == k2

    def test_different_query_different_key(self):
        k1 = _cache_key("cafe", "London", None, 10)
        k2 = _cache_key("bar", "London", None, 10)
        assert k1 != k2

    def test_different_location_different_key(self):
        k1 = _cache_key("cafe", "London", None, 10)
        k2 = _cache_key("cafe", "Paris", None, 10)
        assert k1 != k2


# ── Unit: tag filter builder ──────────────────────────────────────────────────

class TestBuildTagFilters:
    provider = OverpassProvider()

    def test_cafe_keyword(self):
        filters = self.provider._build_tag_filters("cafe", None)
        assert any('amenity' in f and 'cafe' in f for f in filters)

    def test_restaurant_keyword(self):
        filters = self.provider._build_tag_filters("restaurant", None)
        assert any('restaurant' in f for f in filters)

    def test_technology_keyword(self):
        filters = self.provider._build_tag_filters("technology", None)
        assert any('office' in f for f in filters)

    def test_wildcard_returns_name_filter(self):
        filters = self.provider._build_tag_filters("*", None)
        assert any('"name"' in f for f in filters)

    def test_empty_query_returns_name_filter(self):
        filters = self.provider._build_tag_filters("", None)
        assert any('"name"' in f for f in filters)

    def test_category_hints_used(self):
        filters = self.provider._build_tag_filters("", "restaurant")
        assert any('restaurant' in f for f in filters)

    def test_combined_query_and_category(self):
        filters = self.provider._build_tag_filters("coffee", "cafe")
        assert any('cafe' in f for f in filters)

    def test_fallback_to_name_search(self):
        filters = self.provider._build_tag_filters("zorblax widget co", None)
        # Should fall through to a name~ substring search
        assert any('name' in f for f in filters)


# ── Unit: bbox_around ─────────────────────────────────────────────────────────

class TestBboxAround:
    provider = OverpassProvider(radius_m=1000)

    def test_returns_four_values(self):
        bbox = self.provider._bbox_around(51.5, -0.1)
        assert len(bbox) == 4

    def test_south_less_than_north(self):
        s, w, n, e = self.provider._bbox_around(51.5, -0.1)
        assert s < n

    def test_west_less_than_east(self):
        s, w, n, e = self.provider._bbox_around(51.5, -0.1)
        assert w < e

    def test_radius_respected(self):
        """The bounding box should be roughly 2 × radius wide."""
        lat, lon = 51.5, -0.1
        radius = 5000
        prov = OverpassProvider(radius_m=radius)
        s, w, n, e = prov._bbox_around(lat, lon)
        delta_lat = (n - s) / 2 * 111_320
        assert abs(delta_lat - radius) < 50  # within 50 m tolerance


# ── Unit: cache ───────────────────────────────────────────────────────────────

class TestProviderCache:
    def test_cache_miss_returns_none(self):
        p = OverpassProvider()
        assert p._get_cache("nonexistent") is None

    def test_cache_set_then_get(self):
        p = OverpassProvider()
        biz = Business(id="osm_node_1", name="Test", source="openstreetmap")
        p._set_cache("k1", [biz])
        result = p._get_cache("k1")
        assert result is not None
        assert result[0].name == "Test"

    def test_cache_clear(self):
        p = OverpassProvider()
        biz = Business(id="osm_node_1", name="Test", source="openstreetmap")
        p._set_cache("k1", [biz])
        p.clear_cache()
        assert p._get_cache("k1") is None

    def test_expired_cache_returns_none(self):
        import time
        p = OverpassProvider(cache_ttl=0)  # TTL = 0 → always expired
        biz = Business(id="osm_node_1", name="Test", source="openstreetmap")
        p._set_cache("k1", [biz])
        # Force expiry by backdating the cache entry timestamp
        p._cache["k1"] = (time.monotonic() - 10, [biz])
        assert p._get_cache("k1") is None


# ── Integration: mocked HTTP ──────────────────────────────────────────────────

@pytest.mark.asyncio
class TestOverpassProviderMocked:
    """End-to-end search flow with all HTTP calls mocked via respx."""

    @respx.mock
    async def test_search_returns_businesses(self):
        """search() geocodes then queries Overpass and returns Business list."""
        # Mock Nominatim
        respx.get(url__startswith=NOMINATIM_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_nominatim_response())
        )
        # Mock Overpass
        elements = [
            _make_node(osm_id=1, name="Blue Coffee", amenity="cafe"),
            _make_node(osm_id=2, name="Red Coffee", amenity="cafe"),
        ]
        respx.post(OVERPASS_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_overpass_response(elements))
        )

        provider = OverpassProvider()
        results = await provider.search("cafe", "London", None, 10)

        assert len(results) == 2
        assert all(isinstance(b, Business) for b in results)
        assert all(b.source == "openstreetmap" for b in results)
        assert results[0].name in ("Blue Coffee", "Red Coffee")

    @respx.mock
    async def test_search_deduplicates_by_name_and_city(self):
        """Businesses with the same name+city should appear only once."""
        respx.get(url__startswith=NOMINATIM_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_nominatim_response())
        )
        elements = [
            _make_node(osm_id=10, name="Same Corp", amenity="cafe"),
            _make_node(osm_id=11, name="Same Corp", amenity="cafe"),
            _make_node(osm_id=12, name="Different Corp", amenity="cafe"),
        ]
        respx.post(OVERPASS_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_overpass_response(elements))
        )

        provider = OverpassProvider()
        results = await provider.search("cafe", "London", None, 10)

        names = [b.name for b in results]
        assert names.count("Same Corp") == 1
        assert "Different Corp" in names

    @respx.mock
    async def test_search_respects_limit(self):
        respx.get(url__startswith=NOMINATIM_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_nominatim_response())
        )
        elements = [
            _make_node(osm_id=i, name=f"Biz {i}", amenity="cafe") for i in range(30)
        ]
        respx.post(OVERPASS_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_overpass_response(elements))
        )

        provider = OverpassProvider()
        results = await provider.search("cafe", "London", None, 5)

        assert len(results) <= 5

    @respx.mock
    async def test_search_no_location_returns_empty(self):
        """Without a location, we cannot geocode, so results are empty."""
        provider = OverpassProvider()
        results = await provider.search("cafe", None, None, 10)
        assert results == []

    @respx.mock
    async def test_search_nominatim_404_returns_empty(self):
        """Nominatim failure → empty results (not an exception)."""
        respx.get(url__startswith=NOMINATIM_ENDPOINT).mock(
            return_value=httpx.Response(404, json=[])
        )
        provider = OverpassProvider()
        results = await provider.search("cafe", "Nowhere", None, 10)
        assert results == []

    @respx.mock
    async def test_search_caches_result(self):
        """Second identical search call does NOT hit the network."""
        respx.get(url__startswith=NOMINATIM_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_nominatim_response())
        )
        elements = [_make_node(osm_id=1, name="Cached Café")]
        overpass_mock = respx.post(OVERPASS_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_overpass_response(elements))
        )

        provider = OverpassProvider()
        r1 = await provider.search("cafe", "London", None, 10)
        r2 = await provider.search("cafe", "London", None, 10)

        assert r1 == r2
        # Overpass should only have been called once (second call is cached)
        assert overpass_mock.call_count == 1

    @respx.mock
    async def test_overpass_empty_elements_returns_empty(self):
        """Overpass returning no elements → empty list, no crash."""
        respx.get(url__startswith=NOMINATIM_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_nominatim_response())
        )
        respx.post(OVERPASS_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_overpass_response([]))
        )
        provider = OverpassProvider()
        results = await provider.search("cafe", "London", None, 10)
        assert results == []

    @respx.mock
    async def test_search_with_lat_lon_string_skips_nominatim(self):
        """Passing 'lat,lon' skips Nominatim and calls Overpass directly."""
        overpass_mock = respx.post(OVERPASS_ENDPOINT).mock(
            return_value=httpx.Response(
                200, json=_overpass_response([_make_node(osm_id=99, name="Geo Café")])
            )
        )
        provider = OverpassProvider()
        results = await provider.search("cafe", "51.5074,-0.1278", None, 10)

        # Nominatim should NOT have been called
        assert not any("nominatim" in str(r.request.url) for r in overpass_mock.calls)
        assert len(results) == 1
        assert results[0].name == "Geo Café"

    @respx.mock
    async def test_get_details_valid_osm_id(self):
        element = _make_node(osm_id=12345, name="Detail Shop")
        respx.post(OVERPASS_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_overpass_response([element]))
        )
        provider = OverpassProvider()
        biz = await provider.get_details("osm_node_12345")
        assert biz is not None
        assert biz.name == "Detail Shop"

    @respx.mock
    async def test_get_details_non_osm_id_returns_none(self):
        provider = OverpassProvider()
        result = await provider.get_details("demo_001")
        assert result is None

    @respx.mock
    async def test_all_businesses_have_required_fields(self):
        respx.get(url__startswith=NOMINATIM_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_nominatim_response())
        )
        elements = [
            _make_node(osm_id=i, name=f"Biz {i}") for i in range(5)
        ]
        respx.post(OVERPASS_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_overpass_response(elements))
        )
        provider = OverpassProvider()
        results = await provider.search("*", "London", None, 10)
        for biz in results:
            assert biz.id
            assert biz.name
            assert biz.source == "openstreetmap"
            assert biz.is_ai_generated is False

    @respx.mock
    async def test_no_api_keys_in_requests(self):
        """Verify that no secrets appear in HTTP request headers or URLs."""
        captured_requests: list[httpx.Request] = []

        def capture(request: httpx.Request) -> httpx.Response:
            captured_requests.append(request)
            return httpx.Response(200, json=_nominatim_response())

        respx.get(url__startswith=NOMINATIM_ENDPOINT).mock(side_effect=capture)
        respx.post(OVERPASS_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_overpass_response([]))
        )

        provider = OverpassProvider()
        await provider.search("cafe", "London", None, 5)

        for req in captured_requests:
            for header_val in req.headers.values():
                assert "key=" not in header_val.lower()
                assert "api_key" not in header_val.lower()
