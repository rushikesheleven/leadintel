"""
Comprehensive Unit Tests for Step 4: Competitor Intelligence & Business Comparison.

Covers:
- Direct competitors detection
- Indirect competitors detection
- Unrelated businesses rejection (proximity does not equal competition)
- Missing websites and missing categories handling
- Duplicate competitors deduplication
- Competitor with inaccessible website handling
- Side-by-side SEO & social media comparison matrix
- Empty competitor results
- Invalid input handling
- MCP tool execution
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from leadintel.server import mcp
from leadintel.services.business_comparison import compare_target_against_competitors
from leadintel.services.competitor_research import (
    calculate_competitor_relevance,
    find_industry_competitors,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

HTML_COMPETITOR_A = """
<!DOCTYPE html>
<html>
<head>
    <title>Alpha Cloud Services - Enterprise Solutions</title>
    <meta name="description" content="Leading enterprise cloud and SaaS solutions for modern businesses.">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <h1>Alpha Cloud Services</h1>
    <p>Contact us at contact@alphacloud.example</p>
    <a href="https://linkedin.com/company/alphacloud">LinkedIn</a>
    <a href="https://twitter.com/alphacloud">Twitter</a>
    <a href="https://facebook.com/alphacloud">Facebook</a>
    <form action="/contact" method="post"><button type="submit">Submit</button></form>
</body>
</html>
"""

HTML_COMPETITOR_B = """
<!DOCTYPE html>
<html>
<head><title>Beta Tech</title></head>
<body>
    <p>Minimal page without headings or mobile viewport.</p>
</body>
</html>
"""


# ── Competitor Relevance & Taxonomy Tests ─────────────────────────────────────

class TestCompetitorRelevance:
    def test_direct_competitor_exact_category(self):
        conf, ctype, reason = calculate_competitor_relevance(
            target_name="Acme Tech",
            target_category="Software Development",
            candidate_name="Zenith Apps",
            candidate_category="Software Development",
        )
        assert ctype == "direct"
        assert conf >= 0.70
        assert "category alignment" in reason.lower()

    def test_direct_competitor_keyword_overlap(self):
        conf, ctype, reason = calculate_competitor_relevance(
            target_name="Blue Bottle",
            target_category="Coffee Shop",
            candidate_name="Artisan Cafe",
            candidate_category="Coffee Roasters & Cafe",
        )
        assert ctype == "direct"
        assert conf >= 0.70

    def test_indirect_competitor_broader_group(self):
        conf, ctype, reason = calculate_competitor_relevance(
            target_name="CloudStack Systems",
            target_category="Cloud Computing",
            candidate_name="Omni Marketing Group",
            candidate_category="Digital Marketing",
        )
        # Marketing vs Cloud are distinct groups
        assert ctype != "direct"

        # Software vs IT consulting are in same broader technology group
        conf2, ctype2, reason2 = calculate_competitor_relevance(
            target_name="CloudStack Systems",
            target_category="Cloud Computing",
            candidate_name="Omni IT Consulting",
            candidate_category="Consulting",
        )
        assert ctype2 == "indirect"
        assert conf2 >= 0.50

    def test_unrelated_business_different_industry(self):
        conf, ctype, reason = calculate_competitor_relevance(
            target_name="Downtown Dental Clinic",
            target_category="Dentist",
            candidate_name="Super Pizza Palace",
            candidate_category="Restaurant",
        )
        assert ctype == "unrelated"
        assert conf <= 0.20
        assert "Different industry" in reason

    def test_identical_business_is_unrelated(self):
        conf, ctype, reason = calculate_competitor_relevance(
            target_name="Acme Tech Solutions",
            target_category="Software Development",
            candidate_name="Acme Tech Solutions",
            candidate_category="Software Development",
        )
        assert ctype == "unrelated"
        assert "Identical business" in reason

    def test_missing_candidate_category_falls_back_to_name(self):
        conf, ctype, reason = calculate_competitor_relevance(
            target_name="Acme Pizza",
            target_category="Restaurant",
            candidate_name="Gourmet Pizza Slice",
            candidate_category=None,
        )
        assert ctype == "indirect"
        assert "pizza" in reason.lower()

    def test_both_categories_missing_unrelated_if_names_differ(self):
        conf, ctype, reason = calculate_competitor_relevance(
            target_name="Alpha Corp",
            target_category=None,
            candidate_name="Beta Logistics",
            candidate_category=None,
        )
        assert ctype == "unrelated"


# ── Competitor Research Service Tests ─────────────────────────────────────────

@pytest.mark.asyncio
class TestCompetitorResearchService:
    async def test_find_competitors_demo_mode(self):
        results = await find_industry_competitors(
            business_name="Acme Tech Solutions",
            business_category="Software Development",
            city="San Francisco",
            max_competitors=3,
            enrich_websites=False,
        )
        assert "target_business" in results
        assert results["target_business"]["name"] == "Acme Tech Solutions"
        assert isinstance(results["competitors"], list)
        # Should not include Acme Tech Solutions itself
        names = [c["name"] for c in results["competitors"]]
        assert "Acme Tech Solutions" not in names

    async def test_find_competitors_rejects_empty_name(self):
        with pytest.raises(ValueError):
            await find_industry_competitors(business_name="")

    async def test_find_competitors_deduplicates_duplicate_names(self):
        results = await find_industry_competitors(
            business_name="Target Enterprise",
            business_category="Technology",
            city="San Francisco",
            enrich_websites=False,
        )
        names = [c["name"] for c in results["competitors"]]
        assert len(names) == len(set(names))

    @respx.mock
    async def test_find_competitors_with_website_enrichment(self):
        respx.get("https://alphacloud.example/robots.txt").mock(
            return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
        )
        respx.get("https://alphacloud.example").mock(
            return_value=httpx.Response(200, text=HTML_COMPETITOR_A)
        )
        respx.head(url__startswith="https://alphacloud.example/").mock(
            return_value=httpx.Response(200)
        )

        results = await find_industry_competitors(
            business_name="BrightSpark Digital",
            business_category="Digital Marketing",
            city="New York",
            enrich_websites=True,
        )
        assert "competitors" in results


# ── Business Comparison Service Tests ─────────────────────────────────────────

@pytest.mark.asyncio
class TestBusinessComparisonService:
    @respx.mock
    async def test_compare_businesses_full_matrix(self):
        # Target mocks
        respx.get("https://target.example/robots.txt").mock(
            return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
        )
        respx.get("https://target.example/sitemap.xml").mock(
            return_value=httpx.Response(200, text="<xml></xml>")
        )
        respx.get("https://target.example").mock(
            return_value=httpx.Response(200, text=HTML_COMPETITOR_A)
        )
        respx.head(url__startswith="https://target.example/").mock(
            return_value=httpx.Response(200)
        )

        # Competitor mocks
        respx.get("https://comp-beta.example/robots.txt").mock(
            return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
        )
        respx.get("https://comp-beta.example/sitemap.xml").mock(
            return_value=httpx.Response(404)
        )
        respx.get("https://comp-beta.example").mock(
            return_value=httpx.Response(200, text=HTML_COMPETITOR_B)
        )
        respx.head(url__startswith="https://comp-beta.example/").mock(
            return_value=httpx.Response(200)
        )

        target = {
            "name": "Target Alpha Corp",
            "website": "https://target.example",
            "category": "Cloud Services",
        }
        competitors = [
            {
                "name": "Competitor Beta",
                "website": "https://comp-beta.example",
                "category": "Cloud Services",
            },
            {
                "name": "Competitor No-Site",
                "website": None,
                "category": "Cloud Services",
            },
        ]

        report = await compare_target_against_competitors(target, competitors)

        assert report["target_business"] == "Target Alpha Corp"
        assert report["competitors_compared_count"] == 2
        assert len(report["comparison_matrix"]) == 3  # Target + 2 competitors

        # Check matrix fields
        target_row = next(r for r in report["comparison_matrix"] if r["role"] == "Target")
        assert target_row["https_secure"] == "Yes"
        assert target_row["mobile_ready"] == "Yes"
        assert target_row["seo_score"] > 0
        assert "linkedin" in target_row["social_channels"].lower()

        # Check Strengths & Opportunities
        assert len(report["strengths"]) > 0
        assert len(report["opportunities"]) > 0
        assert "Target Alpha Corp" in report["competitive_positioning_summary"]

    async def test_compare_empty_competitors(self):
        target = {"name": "Solo Venture", "website": "https://solo.example"}
        report = await compare_target_against_competitors(target, [])
        assert report["competitors_compared_count"] == 0
        assert "No local competitors identified" in report["strengths"][0]

    async def test_compare_inaccessible_competitor_website(self):
        target = {"name": "Target Co", "website": None}
        competitors = [{"name": "Broken Co", "website": "https://broken.invalid.example"}]
        report = await compare_target_against_competitors(target, competitors)
        assert report["competitors_compared_count"] == 1
        broken_row = next(r for r in report["comparison_matrix"] if r["name"] == "Broken Co")
        assert broken_row["website_available"] == "No"


# ── MCP Tools Integration Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
class TestMcpToolsCompetitorIntelligence:
    async def test_mcp_find_competitors(self):
        res = await mcp.call_tool("find_competitors", {
            "business_name": "Acme Tech Solutions",
            "business_category": "Software Development",
            "city": "San Francisco",
            "enrich_websites": False,
        })
        content = res.content[0].text if hasattr(res.content[0], "text") else res.content[0]
        data = json.loads(content) if isinstance(content, str) else content

        assert "competitors" in data
        assert "target_business" in data
        assert data["target_business"]["name"] == "Acme Tech Solutions"

    async def test_mcp_compare_businesses(self):
        res = await mcp.call_tool("compare_businesses", {
            "target_business": {"name": "Target Enterprise", "category": "Consulting"},
            "competitor_businesses": [
                {"name": "Competitor One", "category": "Consulting"},
            ],
        })
        content = res.content[0].text if hasattr(res.content[0], "text") else res.content[0]
        data = json.loads(content) if isinstance(content, str) else content

        assert data["target_business"] == "Target Enterprise"
        assert len(data["comparison_matrix"]) == 2
        assert "competitive_positioning_summary" in data
