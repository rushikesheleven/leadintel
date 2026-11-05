"""
Comprehensive Regression & Feature Test Suite for LeadIntel v0.2.0.

Covers:
1. Pune city-centre search (central POIs included: Shivajinagar, FC Road, Deccan, Kothrud, Koregaon Park).
2. Explicit coordinate search (lat, lon) and radius enforcement.
3. Strict neighbouring municipality exclusion (Alandi & Pimpri excluded from central search).
4. Wider metropolitan search option (wider_metro=True includes outlying towns).
5. Category accuracy & expansion for food/restaurants.
6. Road / infrastructure false-positive rejection (FC Road highway, bus stops, waterways rejected).
7. Website opportunity identification and deterministic scoring:
   - website_verified (good vs outdated/weak sites)
   - website_not_found_after_research (score 90–100)
   - website_broken (score 75–89)
   - website_unverified
   - website_not_checked (missing OSM site without research)
8. Directory & aggregator detection (Justdial, Sulekha, Indiamart, Zomato, Yelp rejected as official sites).
9. Domain ownership verification (token matching).
10. Multi-criteria ranking (highest_website_opportunity ranks sites without websites first, closest sorts by distance).
11. Data confidence calculation.
12. MCP search_businesses integration test.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from leadintel.models.business import Business
from leadintel.providers.demo_provider import DemoProvider
from leadintel.providers.overpass_provider import (
    haversine_distance_meters,
    is_valid_business_element,
)
from leadintel.server import mcp
from leadintel.services.website_opportunity import (
    batch_evaluate_websites,
    evaluate_business_website,
    is_directory_or_social_domain,
    is_domain_belonging_to_business,
)
from leadintel.tools.search_businesses import _apply_ranking, _compute_data_confidence

# ── 1. Geographic Precision & Distance Calculations ───────────────────────────


class TestGeographicPrecision:
    def test_haversine_distance_calculation(self):
        # Distance between Shaniwar Wada (Pune Center: 18.5204, 73.8567)
        # and Vaishali on FC Road (18.5246, 73.8415) is ~1.7 km
        dist = haversine_distance_meters(18.5204, 73.8567, 18.5246, 73.8415)
        assert 1600 <= dist <= 1800

        # Distance to Alandi (18.6775, 73.8967) is ~18 km
        dist_alandi = haversine_distance_meters(18.5204, 73.8567, 18.6775, 73.8967)
        assert 17000 <= dist_alandi <= 19000

        # Distance to Pimpri (18.6279, 73.8009) is ~13.3 km
        dist_pimpri = haversine_distance_meters(18.5204, 73.8567, 18.6279, 73.8009)
        assert 13000 <= dist_pimpri <= 14000

    @pytest.mark.asyncio
    async def test_pune_city_centre_excludes_distant_municipalities(self):
        provider = DemoProvider()
        # Search central Pune
        results = await provider.search(
            query="*",
            location="Pune",
            radius_meters=6000,
            wider_metro=False,
            limit=20,
        )
        names = [b.name for b in results]

        # Central Pune businesses must be included
        assert "Vaishali Restaurant" in names
        assert "Cafe Goodluck" in names
        assert "German Bakery" in names
        assert "Kothrud Software Labs" in names

        # Distant municipalities MUST be excluded
        assert "Alandi Pilgrim Refreshments" not in names
        assert "Pimpri Auto Spare Parts" not in names

        # All returned businesses must have distances <= 6000m
        for b in results:
            if b.distance_meters is not None:
                assert b.distance_meters <= 6000
                assert b.distance_km is not None
                assert b.distance_km <= 6.0

    @pytest.mark.asyncio
    async def test_wider_metro_includes_distant_municipalities(self):
        provider = DemoProvider()
        # Search wider Pune metropolitan area
        results = await provider.search(
            query="*",
            location="Pune",
            wider_metro=True,
            limit=20,
        )
        names = [b.name for b in results]

        # In wider metro, Alandi and Pimpri can be included
        assert "Alandi Pilgrim Refreshments" in names
        assert "Pimpri Auto Spare Parts" in names

    @pytest.mark.asyncio
    async def test_explicit_coordinate_search(self):
        provider = DemoProvider()
        # Search centered on FC Road (18.5246, 73.8415) with tight 1km radius
        results = await provider.search(
            query="*",
            latitude=18.5246,
            longitude=73.8415,
            radius_meters=1500,
            limit=10,
        )
        names = [b.name for b in results]

        # Vaishali and Cafe Goodluck are right there
        assert "Vaishali Restaurant" in names
        assert "Cafe Goodluck" in names

        # German Bakery (Koregaon Park ~5km away) and Alandi (18km away) must be excluded
        assert "German Bakery" not in names
        assert "Alandi Pilgrim Refreshments" not in names


# ── 2. Category Accuracy & Infrastructure Rejection ───────────────────────────


class TestCategoryAndInfrastructureValidation:
    def test_reject_highway_road_ways(self):
        # A road way tagged highway=primary with name="Fergusson College Road"
        road_element = {
            "type": "way",
            "id": 123456,
            "center": {"lat": 18.5246, "lon": 73.8415},
            "tags": {
                "name": "Fergusson College Road",
                "highway": "primary",
                "ref": "SH 114",
            },
        }
        assert is_valid_business_element(road_element) is False

    def test_reject_bus_stop_node(self):
        bus_stop = {
            "type": "node",
            "id": 987654,
            "lat": 18.5246,
            "lon": 73.8415,
            "tags": {
                "name": "Deccan Gymkhana Bus Station",
                "highway": "bus_stop",
                "public_transport": "platform",
            },
        }
        assert is_valid_business_element(bus_stop) is False

    def test_reject_waterway_and_natural_features(self):
        river = {
            "type": "way",
            "id": 112233,
            "tags": {
                "name": "Mutha River",
                "waterway": "river",
            },
        }
        assert is_valid_business_element(river) is False

    def test_reject_suburb_place_without_business_tag(self):
        suburb = {
            "type": "node",
            "id": 445566,
            "lat": 18.5314,
            "lon": 73.8446,
            "tags": {
                "name": "Shivajinagar",
                "place": "suburb",
            },
        }
        assert is_valid_business_element(suburb) is False

    def test_accept_commercial_restaurant_poi(self):
        restaurant = {
            "type": "node",
            "id": 556677,
            "lat": 18.5246,
            "lon": 73.8415,
            "tags": {
                "name": "Vaishali",
                "amenity": "restaurant",
                "cuisine": "south_indian",
            },
        }
        assert is_valid_business_element(restaurant) is True

    def test_accept_office_poi(self):
        office = {
            "type": "way",
            "id": 889900,
            "center": {"lat": 18.5074, "lon": 73.8077},
            "tags": {
                "name": "Pune Tech Hub",
                "office": "it",
            },
        }
        assert is_valid_business_element(office) is True


# ── 3. Directory & Social Media Domain Identification ─────────────────────────


class TestDirectoryAndSocialDetection:
    def test_indian_directories_detected(self):
        assert is_directory_or_social_domain("https://www.justdial.com/Pune/Vaishali") is True
        assert is_directory_or_social_domain("https://sulekha.com/pune/restaurants") is True
        assert is_directory_or_social_domain("https://dir.indiamart.com/pune/") is True
        assert is_directory_or_social_domain("https://www.zomato.com/pune/cafe-goodluck") is True
        assert is_directory_or_social_domain("https://www.swiggy.com/restaurants/vaishali") is True
        assert is_directory_or_social_domain("https://magicpin.in/pune/restaurant") is True

    def test_global_directories_and_social_detected(self):
        assert is_directory_or_social_domain("https://www.yelp.com/biz/some-cafe") is True
        assert is_directory_or_social_domain("https://www.tripadvisor.com/Restaurant_Review") is True
        assert is_directory_or_social_domain("https://facebook.com/vaishalipune") is True
        assert is_directory_or_social_domain("https://www.instagram.com/cafegoodluck") is True

    def test_genuine_business_domains_not_flagged_as_directory(self):
        assert is_directory_or_social_domain("https://vaishalihotel.in") is False
        assert is_directory_or_social_domain("https://cafegoodluck.com") is False
        assert is_directory_or_social_domain("https://germanbakerypune.in") is False

    def test_domain_matching_to_business_name(self):
        assert is_domain_belonging_to_business("vaishalihotel.in", "Vaishali Restaurant") is True
        assert is_domain_belonging_to_business("cafegoodluck.com", "Cafe Goodluck") is True
        assert is_domain_belonging_to_business("germanbakerypune.com", "German Bakery") is True
        # Completely unrelated domain
        assert is_domain_belonging_to_business("randomtechcorp.com", "Vaishali Restaurant") is False


# ── 4. Website Opportunity Scoring & Status States ────────────────────────────


@pytest.mark.asyncio
class TestWebsiteOpportunityEvaluation:
    @respx.mock
    async def test_verified_good_website_low_opportunity(self):
        good_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>German Bakery Pune - Authentic Bakery & Cafe</title>
            <meta name="description" content="Famous European bakery and cafe in Koregaon Park, Pune.">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body><h1>Welcome to German Bakery</h1></body>
        </html>
        """
        respx.get("https://germanbakery.example").mock(
            return_value=httpx.Response(200, text=good_html)
        )

        biz = Business(
            id="biz_gb",
            name="German Bakery",
            website="https://germanbakery.example",
            city="Pune",
        )
        evaluated = await evaluate_business_website(biz, research_missing=False)

        assert evaluated.website_status == "website_verified"
        assert evaluated.website_opportunity_score is not None
        assert 5.0 <= evaluated.website_opportunity_score <= 29.0  # Good website range

    @respx.mock
    async def test_verified_outdated_website_medium_high_opportunity(self):
        # Missing mobile viewport
        outdated_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Old Web Corp</title></head>
        <body><p>No viewport meta tag.</p></body>
        </html>
        """
        respx.get("https://oldwebcorp.example").mock(
            return_value=httpx.Response(200, text=outdated_html)
        )

        biz = Business(
            id="biz_old",
            name="Old Web Corp",
            website="https://oldwebcorp.example",
        )
        evaluated = await evaluate_business_website(biz, research_missing=False)

        assert evaluated.website_status == "website_verified"
        assert evaluated.website_opportunity_score is not None
        # Outdated range: 50–74
        assert 50.0 <= evaluated.website_opportunity_score <= 74.0
        assert "outdated" in (evaluated.website_opportunity_explanation or "").lower()

    @respx.mock
    async def test_broken_website_detected(self):
        respx.get("https://brokenbiz.example").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        biz = Business(
            id="biz_broken",
            name="Broken Biz Co",
            website="https://brokenbiz.example",
        )
        evaluated = await evaluate_business_website(biz, research_missing=False)

        assert evaluated.website_status == "website_broken"
        assert evaluated.website_opportunity_score is not None
        # Broken range: 75–89
        assert 75.0 <= evaluated.website_opportunity_score <= 89.0
        assert "broken" in (evaluated.website_opportunity_explanation or "").lower()

    @respx.mock
    async def test_no_website_after_research_highest_opportunity(self):
        # Mock DuckDuckGo returning 200 with no relevant non-directory results
        respx.get(url__startswith="https://html.duckduckgo.com/html/").mock(
            return_value=httpx.Response(200, text="<html><body><p>No organic results</p></body></html>")
        )

        biz = Business(
            id="biz_nosite",
            name="Vaishali Restaurant",
            website=None,
            city="Pune",
        )
        evaluated = await evaluate_business_website(biz, location="Pune", research_missing=True)

        assert evaluated.website_status == "website_not_found_after_research"
        assert evaluated.website_opportunity_score is not None
        # No website found range: 90–100
        assert 90.0 <= evaluated.website_opportunity_score <= 100.0
        assert "No official website found after thorough web research" in (
            evaluated.website_opportunity_explanation or ""
        )

    async def test_empty_osm_website_without_research_is_website_not_checked(self):
        biz = Business(
            id="biz_untested",
            name="Local Store",
            website=None,
        )
        assert biz.website_status == "website_not_checked"
        assert biz.website_opportunity_score is None

    @respx.mock
    async def test_response_truncation_over_200k_bytes(self):
        huge_html = "<html><head><title>Huge Page</title><meta name='description' content='Huge Description'><meta name='viewport' content='width=device-width'></head><body>" + ("X" * 300_000) + "</body></html>"
        respx.get("https://hugebiz.example").mock(
            return_value=httpx.Response(200, text=huge_html)
        )

        biz = Business(
            id="biz_huge",
            name="Huge Biz",
            website="https://hugebiz.example",
        )
        evaluated = await evaluate_business_website(biz, research_missing=False)
        assert evaluated.website_status == "website_verified"
        assert evaluated.website_opportunity_score == 15.0

    @respx.mock
    async def test_batch_evaluate_global_timeout_aborts_gracefully(self):
        import asyncio

        async def slow_stream(request):
            await asyncio.sleep(2.0)
            return httpx.Response(200, text="done")

        respx.get("https://slowcorp.example").mock(side_effect=slow_stream)

        biz = Business(
            id="biz_timeout",
            name="Slow Corp",
            website="https://slowcorp.example",
        )
        results = await batch_evaluate_websites(
            businesses=[biz],
            research_missing=False,
            global_timeout=0.05,
        )
        assert len(results) == 1
        res = results[0]
        assert res.website_status == "website_not_checked"
        assert res.website_opportunity_score is None
        assert "prevent system timeout" in (res.website_opportunity_explanation or "")


# ── 5. Multi-Criteria Ranking & Sorting ───────────────────────────────────────


class TestRankingSystem:
    def test_highest_website_opportunity_ranks_no_website_first(self):
        b1 = Business(
            id="1",
            name="Good Site Corp",
            website="https://goodsite.example",
            website_status="website_verified",
            website_opportunity_score=15.0,
            distance_meters=500.0,
            distance_km=0.5,
        )
        b2 = Business(
            id="2",
            name="No Site Cafe",
            website=None,
            website_status="website_not_found_after_research",
            website_opportunity_score=95.0,
            distance_meters=1200.0,
            distance_km=1.2,
        )
        b3 = Business(
            id="3",
            name="Broken Site Co",
            website="https://broken.example",
            website_status="website_broken",
            website_opportunity_score=80.0,
            distance_meters=800.0,
            distance_km=0.8,
        )

        ranked = _apply_ranking([b1, b2, b3], sort_by="highest_website_opportunity")

        # Prioritized order: No Site (95) -> Broken Site (80) -> Good Site (15)
        assert ranked[0].id == "2"
        assert ranked[1].id == "3"
        assert ranked[2].id == "1"

        # Check ranking explanations
        assert "Ranked #1" in ranked[0].ranking_explanation
        assert "High-priority web development opportunity" in ranked[0].ranking_explanation
        assert "Ranked #2" in ranked[1].ranking_explanation
        assert "Broken website detected" in ranked[1].ranking_explanation

    def test_closest_sorting(self):
        b1 = Business(
            id="1",
            name="Far Corp",
            distance_meters=5000.0,
            distance_km=5.0,
            website_opportunity_score=95.0,
        )
        b2 = Business(
            id="2",
            name="Near Corp",
            distance_meters=300.0,
            distance_km=0.3,
            website_opportunity_score=15.0,
        )

        ranked = _apply_ranking([b1, b2], sort_by="closest")
        assert ranked[0].id == "2"
        assert ranked[1].id == "1"


# ── 6. Data Confidence ────────────────────────────────────────────────────────


class TestDataConfidence:
    def test_full_business_record_has_high_confidence(self):
        biz = Business(
            id="biz_full",
            name="Enterprise Co",
            category="Technology",
            address="123 High St, Pune",
            latitude=18.52,
            longitude=73.85,
            phone="+91-20-12345678",
            email="contact@enterprise.example",
            website="https://enterprise.example",
            website_status="website_verified",
            osm_tags={"amenity": "office", "name": "Enterprise Co"},
        )
        conf = _compute_data_confidence(biz)
        assert conf >= 0.85

    def test_minimal_record_has_lower_confidence(self):
        biz = Business(
            id="biz_sparse",
            name="Sparse Co",
            website_status="website_not_checked",
        )
        conf = _compute_data_confidence(biz)
        assert conf <= 0.35


# ── 7. MCP Tool search_businesses Integration ─────────────────────────────────


@pytest.mark.asyncio
class TestMcpSearchBusinessesV020:
    async def test_search_businesses_pune_returns_complete_model(self):
        res = await mcp.call_tool("search_businesses", {
            "query": "*",
            "location": "Pune",
            "category": "Food & Beverage",
            "limit": 5,
            "sort_by": "highest_website_opportunity",
        })
        content = res.content[0].text if hasattr(res.content[0], "text") else res.content[0]
        import json
        data = json.loads(content) if isinstance(content, str) else content

        assert "businesses" in data
        assert "total_found" in data
        assert data["sort_by"] == "highest_website_opportunity"

        # Inspect returned businesses
        for b in data["businesses"]:
            assert "name" in b
            assert "website_status" in b
            assert b["website_status"] in (
                "website_verified",
                "website_not_found_after_research",
                "website_unverified",
                "website_broken",
                "website_not_checked",
            )
            assert "data_confidence" in b
            assert "ranking_explanation" in b


# ── 8. CMS and Contact Route Detection Tests ─────────────────────────────────

@pytest.mark.asyncio
class TestCmsAndContactRouteDetection:
    @respx.mock
    async def test_wordpress_and_missing_contact_route(self):
        html = """
        <html>
            <head>
                <title>WP Agency</title>
                <meta name="description" content="A great WP agency">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <link rel="stylesheet" href="/wp-content/themes/twentytwenty/style.css">
            </head>
            <body>
                <h1>Welcome</h1>
                <a href="/services">Our Services</a>
            </body>
        </html>
        """
        respx.get("https://wpagency.example").mock(
            return_value=httpx.Response(200, text=html)
        )

        biz = Business(
            id="biz_wp",
            name="WP Agency",
            website="https://wpagency.example",
        )
        evaluated = await evaluate_business_website(biz, research_missing=False)

        assert evaluated.detected_cms == "WordPress"
        assert evaluated.has_contact_route is False
        assert "Built on WordPress." in (evaluated.website_opportunity_explanation or "")
        assert "Missing a clear contact page." in (evaluated.website_opportunity_explanation or "")

    @respx.mock
    async def test_shopify_and_contact_route_mailto(self):
        html = """
        <html>
            <head>
                <title>Fashion Store</title>
                <meta name="description" content="Shop trends">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <script src="https://cdn.shopify.com/s/files/1/script.js"></script>
            </head>
            <body>
                <a href="mailto:support@fashionstore.example">Email Us</a>
            </body>
        </html>
        """
        respx.get("https://fashionstore.example").mock(
            return_value=httpx.Response(200, text=html)
        )

        biz = Business(
            id="biz_shopify",
            name="Fashion Store",
            website="https://fashionstore.example",
        )
        evaluated = await evaluate_business_website(biz, research_missing=False)

        assert evaluated.detected_cms == "Shopify"
        assert evaluated.has_contact_route is True
        assert "Built on Shopify." in (evaluated.website_opportunity_explanation or "")
        assert "Missing a clear contact page." not in (evaluated.website_opportunity_explanation or "")

    @respx.mock
    async def test_wix_and_squarespace_detection(self):
        wix_html = "<html><head><title>Wix Site</title><meta name='description' content='d'><meta name='viewport' content='width=device-width'></head><body><script src='https://static.wixstatic.com/wixsite/app.js'></script><a href='/contact-us'>Contact</a></body></html>"
        respx.get("https://wixsite.example").mock(return_value=httpx.Response(200, text=wix_html))

        biz_wix = Business(id="biz_wix", name="Wix Site", website="https://wixsite.example")
        eval_wix = await evaluate_business_website(biz_wix, research_missing=False)
        assert eval_wix.detected_cms == "Wix"
        assert eval_wix.has_contact_route is True

        sq_html = "<html><head><title>SQ Site</title><meta name='description' content='d'><meta name='viewport' content='width=device-width'></head><body><script src='https://assets.squarespace.com/common.js'></script><a href='/about'>About</a></body></html>"
        respx.get("https://sqsite.example").mock(return_value=httpx.Response(200, text=sq_html))

        biz_sq = Business(id="biz_sq", name="SQ Site", website="https://sqsite.example")
        eval_sq = await evaluate_business_website(biz_sq, research_missing=False)
        assert eval_sq.detected_cms == "Squarespace"
        assert eval_sq.has_contact_route is True

    async def test_csv_and_excel_export_include_cms_and_contact_route(self):
        import csv
        import io
        import os
        import tempfile

        import openpyxl

        from leadintel.exporters.csv_exporter import export_to_csv
        from leadintel.exporters.excel_exporter import export_to_excel

        biz = Business(
            id="biz_export_test",
            name="Export Test Corp",
            website="https://exporttestcorp.example",
            detected_cms="WordPress",
            has_contact_route=False,
            website_status="website_verified",
            website_opportunity_score=65.0,
        )

        # 1. Test CSV
        csv_str = export_to_csv([biz])
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 1
        assert "detected_cms" in rows[0]
        assert "has_contact_route" in rows[0]
        assert rows[0]["detected_cms"] == "WordPress"
        assert rows[0]["has_contact_route"] in ("False", "false")

        # 2. Test Excel
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            temp_path = f.name
        try:
            export_to_excel(businesses=[biz.model_dump()], output_path=temp_path)
            wb = openpyxl.load_workbook(temp_path)
            ws_leads = wb["Business Leads"]
            headers = [ws_leads.cell(row=1, column=c).value for c in range(1, 17)]
            assert "CMS" in headers
            assert "Contact Route" in headers
            cms_col = headers.index("CMS") + 1
            contact_col = headers.index("Contact Route") + 1
            assert ws_leads.cell(row=2, column=cms_col).value == "WordPress"
            assert ws_leads.cell(row=2, column=contact_col).value is False
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

