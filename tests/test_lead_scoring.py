"""
Comprehensive Unit Tests for Step 5: Business Lead Scoring.

Covers:
- Business with no website (high web dev opportunity)
- Business with excellent website (high score, low dev opportunity)
- Poor SEO scenarios
- Missing social profiles
- Strong social presence but weak website
- Incomplete business information handling (evidence completeness)
- Missing competitor data handling
- Invalid inputs handling
- Deterministic scoring consistency
- Maximum score ceiling of 100
- score_lead MCP tool execution
"""

from __future__ import annotations

import json

import pytest

from leadintel.server import mcp
from leadintel.services.lead_scoring import score_business_lead

# ── Sample Fixtures ───────────────────────────────────────────────────────────

EXCELLENT_WEBSITE = {
    "available": True,
    "http_status": 200,
    "response_time_seconds": 0.45,
    "protocol": {"is_https": True, "ssl_valid": True},
    "metadata": {"has_mobile_viewport": True, "title": "Top Solutions"},
    "content_structure": {"h1_headings": ["Welcome"], "images_total": 4, "images_missing_alt": 0},
    "contact_detection": {
        "has_contact_form": True,
        "emails_found": ["contact@top.example"],
        "phones_found": ["+1-555-0100"],
    },
    "social_profiles": {
        "linkedin": [{"url": "https://linkedin.com/company/top"}],
        "facebook": [{"url": "https://facebook.com/top"}],
        "twitter": [{"url": "https://twitter.com/top"}],
        "instagram": [{"url": "https://instagram.com/top"}],
    },
}

EXCELLENT_SEO = {
    "seo_score": 92.0,
    "issues": [],
}

POOR_SEO = {
    "seo_score": 25.0,
    "issues": [
        {"level": "error", "message": "Missing H1 heading."},
        {"level": "error", "message": "Missing meta description."},
        {"level": "warning", "message": "No canonical tag."},
    ],
}

STRONG_SOCIAL = {
    "linkedin": [{"url": "https://linkedin.com/company/strong"}],
    "facebook": [{"url": "https://facebook.com/strong"}],
    "twitter": [{"url": "https://twitter.com/strong"}],
    "instagram": [{"url": "https://instagram.com/strong"}],
    "youtube": [{"url": "https://youtube.com/@strong"}],
}

EMPTY_SOCIAL = {
    "linkedin": [],
    "facebook": [],
    "twitter": [],
    "instagram": [],
    "youtube": [],
    "pinterest": [],
}


# ── Scoring Engine Tests ──────────────────────────────────────────────────────

class TestLeadScoringEngine:
    def test_max_score_ceiling_is_100(self):
        result = score_business_lead(
            business_name="Peak Enterprise",
            business_category="Cloud Architecture",
            website_analysis=EXCELLENT_WEBSITE,
            seo_audit=EXCELLENT_SEO,
            social_profiles=STRONG_SOCIAL,
            contact_info={"email": "a@a.com", "phone": "123", "city": "SF"},
            competitor_comparison={"comparison_matrix": [{"role": "Target", "seo_score": 95}]},
        )
        assert result["overall_lead_score"] <= 100.0
        assert result["priority_classification"] == "High Priority"
        assert result["evidence_completeness_percentage"] == 100.0
        assert result["confidence_level"] == "High"

    def test_business_with_no_website(self):
        result = score_business_lead(
            business_name="Local Plumbing Pros",
            business_category="Home Services",
            website_analysis={"available": False, "error": "No domain registered"},
            contact_info={"phone": "+1-555-0999"},
        )
        assert result["overall_lead_score"] < 60.0
        # Website development opportunity should be very high
        assert result["service_opportunities"]["website_development"] >= 90.0
        assert result["recommended_service_package"] == "Website Development"
        assert any("inaccessible" in iss.lower() for iss in result["verified_issues"])

    def test_business_with_poor_seo(self):
        result = score_business_lead(
            business_name="Midtown Law Firm",
            business_category="Legal Services",
            website_analysis=EXCELLENT_WEBSITE,
            seo_audit=POOR_SEO,
            social_profiles=STRONG_SOCIAL,
        )
        # Category score for SEO should be proportionally low
        assert result["category_scores"]["technical_seo"] <= 6.0
        # SEO Opportunity should be high
        assert result["service_opportunities"]["seo_services"] >= 70.0
        assert any("SEO: Missing H1" in iss for iss in result["verified_issues"])

    def test_missing_social_profiles(self):
        result = score_business_lead(
            business_name="Underground Tech",
            business_category="Hardware",
            website_analysis=EXCELLENT_WEBSITE,
            seo_audit=EXCELLENT_SEO,
            social_profiles=EMPTY_SOCIAL,
        )
        assert result["category_scores"]["social_media_presence"] == 0.0
        assert result["service_opportunities"]["social_media_management"] >= 80.0
        assert any("No active social media" in iss for iss in result["verified_issues"])

    def test_strong_social_but_weak_website(self):
        weak_website = {
            "available": True,
            "response_time_seconds": 3.8,
            "protocol": {"is_https": False, "ssl_valid": False},
            "metadata": {"has_mobile_viewport": False},
            "contact_detection": {"has_contact_form": False, "emails_found": [], "phones_found": []},
        }
        result = score_business_lead(
            business_name="Influencer Brand",
            business_category="Fashion Retail",
            website_analysis=weak_website,
            social_profiles=STRONG_SOCIAL,
        )
        # Social score high, mobile/website score low
        assert result["category_scores"]["social_media_presence"] >= 14.0
        assert result["category_scores"]["mobile_experience"] == 0.0
        assert result["service_opportunities"]["website_development"] >= 70.0
        assert any("lacks mobile viewport" in iss for iss in result["verified_issues"])

    def test_incomplete_business_information_penalizes_confidence_not_arbitrary_scores(self):
        # Only business_name provided — zero external evidence
        result = score_business_lead(business_name="Ghost Co")
        assert result["evidence_completeness_percentage"] == 0.0
        assert result["confidence_level"] == "Low"
        assert len(result["missing_information"]) >= 5
        # The engine must still calculate deterministic baseline score without negative numbers or crashing
        assert 0.0 <= result["overall_lead_score"] <= 100.0

    def test_missing_competitor_data_graceful(self):
        result = score_business_lead(
            business_name="Solitary Enterprise",
            business_category="Aerospace",
            website_analysis=EXCELLENT_WEBSITE,
            competitor_comparison=None,
        )
        assert "Competitor benchmark comparison absent." in result["missing_information"]
        assert result["category_scores"]["digital_presence_gaps"] > 0

    def test_scoring_determinism_consistency(self):
        # Same input must return identical output every run
        res1 = score_business_lead(
            business_name="Consistent Corp",
            business_category="Consulting",
            seo_audit={"seo_score": 60.0, "issues": []},
        )
        res2 = score_business_lead(
            business_name="Consistent Corp",
            business_category="Consulting",
            seo_audit={"seo_score": 60.0, "issues": []},
        )
        assert res1["overall_lead_score"] == res2["overall_lead_score"]
        assert res1["category_scores"] == res2["category_scores"]
        assert res1["service_opportunities"] == res2["service_opportunities"]

    def test_rejects_empty_name(self):
        with pytest.raises(ValueError):
            score_business_lead(business_name="")

        with pytest.raises(ValueError):
            score_business_lead(business_name="   ")

    def test_priority_tier_thresholds(self):
        # High priority check
        res_high = score_business_lead(
            business_name="A",
            business_category="Tech",
            website_analysis=EXCELLENT_WEBSITE,
            seo_audit=EXCELLENT_SEO,
            social_profiles=STRONG_SOCIAL,
            contact_info={"email": "a@a.com", "phone": "1", "city": "SF"},
        )
        assert res_high["priority_classification"] == "High Priority"


# ── MCP Tool Execution Tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
class TestScoreLeadMcpTool:
    async def test_mcp_score_lead_invocation(self):
        res = await mcp.call_tool("score_lead", {
            "business_name": "Apex Innovations",
            "business_category": "Software",
            "website_analysis": EXCELLENT_WEBSITE,
            "seo_audit": POOR_SEO,
        })
        content = res.content[0].text if hasattr(res.content[0], "text") else res.content[0]
        data = json.loads(content) if isinstance(content, str) else content

        assert data["business_name"] == "Apex Innovations"
        assert "overall_lead_score" in data
        assert "category_scores" in data
        assert "service_opportunities" in data
        assert "recommended_service_package" in data
        assert data["service_opportunities"]["seo_services"] > 50.0

    async def test_mcp_score_lead_error_handling(self):
        res = await mcp.call_tool("score_lead", {"business_name": ""})
        content = res.content[0].text if hasattr(res.content[0], "text") else res.content[0]
        data = json.loads(content) if isinstance(content, str) else content

        assert "error" in data or data.get("overall_lead_score") == 0.0
