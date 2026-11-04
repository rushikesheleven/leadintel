"""
Lead Scoring Service.

Deterministic, evidence-based lead qualification engine tailored for digital agencies.
Evaluates the digital maturity and addressable gaps of a business without relying on paid APIs or AI tokens.

Core Philosophy:
1. Max 100 points composite score.
2. Missing data is penalized via an Evidence Completeness & Confidence metric, NOT arbitrary negative scores.
3. Distinguishes verified defects (e.g. broken links, missing H1, HTTP without SSL) from absent data.
4. Generates opportunity scores for specific agency services:
   - Website Development Opportunity
   - SEO Improvement Opportunity
   - Social Media Management Opportunity
   - Digital Marketing Opportunity
5. Does not fabricate claims of commercial budget or guaranteed conversion.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Category weights totaling 100 points
CATEGORY_WEIGHTS = {
    "website_quality": 20.0,
    "technical_seo": 20.0,
    "social_media_presence": 15.0,
    "contact_accessibility": 10.0,
    "mobile_experience": 10.0,
    "digital_presence_gaps": 15.0,
    "business_relevance": 10.0,
}


def score_business_lead(
    business_name: str,
    business_category: Optional[str] = None,
    website_analysis: Optional[dict[str, Any]] = None,
    seo_audit: Optional[dict[str, Any]] = None,
    social_profiles: Optional[dict[str, Any]] = None,
    competitor_comparison: Optional[dict[str, Any]] = None,
    contact_info: Optional[dict[str, Any]] = None,
    weights: Optional[dict[str, float]] = None,
) -> dict[str, Any]:
    """
    Score a business lead deterministically across 7 categories.

    Returns structured output containing overall score, priority tier, category breakdown,
    evidence completeness, verified issues, and service package recommendations.
    """
    if not business_name or not isinstance(business_name, str) or not business_name.strip():
        raise ValueError("business_name must be a non-empty string.")

    w = dict(CATEGORY_WEIGHTS)
    if weights:
        w.update(weights)

    verified_issues: list[str] = []
    missing_information: list[str] = []
    evidence_points = 0.0
    total_evidence_possible = 6.0  # Tracking presence of our 6 evidence vectors

    # -------------------------------------------------------------
    # 1. Track Evidence Completeness
    # -------------------------------------------------------------
    if business_category and business_category.strip():
        evidence_points += 1.0
    else:
        missing_information.append("Business category not specified.")

    if website_analysis is not None:
        evidence_points += 1.0
    else:
        missing_information.append("Website technical analysis data absent.")

    if seo_audit is not None:
        evidence_points += 1.0
    else:
        missing_information.append("Technical SEO audit data absent.")

    if social_profiles is not None:
        evidence_points += 1.0
    else:
        missing_information.append("Social media profile scan absent.")

    if contact_info is not None:
        evidence_points += 1.0
    else:
        missing_information.append("Direct contact directory data absent.")

    if competitor_comparison is not None:
        evidence_points += 1.0
    else:
        missing_information.append("Competitor benchmark comparison absent.")

    evidence_completeness_pct = round((evidence_points / total_evidence_possible) * 100, 1)

    if evidence_completeness_pct >= 80:
        confidence_level = "High"
    elif evidence_completeness_pct >= 50:
        confidence_level = "Medium"
    else:
        confidence_level = "Low"

    # -------------------------------------------------------------
    # 2. Category-wise Scoring (Max 100 points)
    # -------------------------------------------------------------
    cat_scores: dict[str, float] = {}

    # Category 1: Website Quality (20 pts)
    # Criteria: Available, HTTPS secure, reasonable response time (< 1.5s), content structure.
    # Note: If no website, agency prospect opportunity for web dev is high, but raw website quality score is low.
    wq_score = 0.0
    if website_analysis:
        if website_analysis.get("available"):
            wq_score += 8.0  # Base availability
            protocol = website_analysis.get("protocol", {})
            if protocol.get("is_https") and protocol.get("ssl_valid"):
                wq_score += 4.0
            else:
                verified_issues.append("Website lacks SSL certificate or is not secured over HTTPS.")

            resp_time = website_analysis.get("response_time_seconds")
            if resp_time is not None:
                if resp_time < 1.0:
                    wq_score += 4.0
                elif resp_time < 2.5:
                    wq_score += 2.0
                else:
                    verified_issues.append(f"Slow initial page response time ({resp_time}s).")

            content = website_analysis.get("content_structure", {})
            if content.get("h1_headings"):
                wq_score += 2.0
            if content.get("images_missing_alt", 0) == 0 and content.get("images_total", 0) > 0:
                wq_score += 2.0
        else:
            verified_issues.append(f"Website is currently inaccessible: {website_analysis.get('error', 'Unreachable')}")
    else:
        # Neutral baseline if information absent
        wq_score = 10.0
    cat_scores["website_quality"] = min(w["website_quality"], round(wq_score, 1))

    # Category 2: Technical SEO (20 pts)
    # Directly normalized from the 0-100 deterministic SEO audit
    t_seo_score = 0.0
    if seo_audit and "seo_score" in seo_audit:
        raw_seo = float(seo_audit.get("seo_score", 0))
        t_seo_score = (raw_seo / 100.0) * w["technical_seo"]
        # Extract verified issues from audit
        for iss in seo_audit.get("issues", []):
            if iss.get("level") in ("error", "warning"):
                verified_issues.append(f"SEO: {iss.get('message')}")
    else:
        t_seo_score = 10.0  # Neutral baseline
    cat_scores["technical_seo"] = min(w["technical_seo"], round(t_seo_score, 1))

    # Category 3: Social Media Presence (15 pts)
    # Criteria: Active channels across LinkedIn, Facebook, Instagram, Twitter/X, YouTube.
    smp_score = 0.0
    total_social_found = 0
    if social_profiles:
        profiles_dict = social_profiles.get("profiles", social_profiles)
        active_channels = []
        for plat, links in profiles_dict.items():
            if isinstance(links, list) and len(links) > 0:
                active_channels.append(plat)
        total_social_found = len(active_channels)

        if total_social_found >= 4:
            smp_score = 15.0
        elif total_social_found == 3:
            smp_score = 12.0
        elif total_social_found == 2:
            smp_score = 8.0
        elif total_social_found == 1:
            smp_score = 4.0
        else:
            verified_issues.append("No active social media profiles detected on the company domain.")
    else:
        smp_score = 7.5  # Neutral baseline
    cat_scores["social_media_presence"] = min(w["social_media_presence"], round(smp_score, 1))

    # Category 4: Contact Accessibility (10 pts)
    # Criteria: Direct email, telephone, and interactive contact form.
    ca_score = 0.0
    has_form = False
    has_email = False
    has_phone = False

    if website_analysis and "contact_detection" in website_analysis:
        cd = website_analysis["contact_detection"]
        has_form = cd.get("has_contact_form", False)
        has_email = len(cd.get("emails_found", [])) > 0
        has_phone = len(cd.get("phones_found", [])) > 0

    if contact_info:
        if contact_info.get("email"):
            has_email = True
        if contact_info.get("phone"):
            has_phone = True

    if has_form:
        ca_score += 4.0
    else:
        verified_issues.append("No digital contact or inquiry form detected.")

    if has_email:
        ca_score += 3.0
    else:
        verified_issues.append("No public contact email address detected.")

    if has_phone:
        ca_score += 3.0
    else:
        verified_issues.append("No direct business phone number detected.")

    cat_scores["contact_accessibility"] = min(w["contact_accessibility"], round(ca_score, 1))

    # Category 5: Mobile Experience (10 pts)
    # Criteria: Explicit viewport meta tag configuration for mobile responsiveness.
    me_score = 0.0
    if website_analysis and "metadata" in website_analysis:
        if website_analysis["metadata"].get("has_mobile_viewport"):
            me_score = 10.0
        else:
            verified_issues.append("Website lacks mobile viewport configuration (poor mobile responsiveness).")
    else:
        me_score = 5.0  # Neutral baseline
    cat_scores["mobile_experience"] = min(w["mobile_experience"], round(me_score, 1))

    # Category 6: Digital Presence Gaps (15 pts)
    # Measures agency prospecting leverage: companies with identifiable gaps or lagging competitors
    # are better suited for digital agency intervention.
    dpg_score = 0.0
    if competitor_comparison and "comparison_matrix" in competitor_comparison:
        matrix = competitor_comparison.get("comparison_matrix", [])
        if len(matrix) > 1:
            target_row = next((r for r in matrix if r.get("role") == "Target"), None)
            comp_rows = [r for r in matrix if r.get("role") == "Competitor"]
            if target_row and comp_rows:
                target_seo = target_row.get("seo_score", 0)
                comp_seos = [r.get("seo_score", 0) for r in comp_rows if r.get("seo_score", 0) > 0]
                avg_comp_seo = (sum(comp_seos) / len(comp_seos)) if comp_seos else 50
                if target_seo < avg_comp_seo:
                    dpg_score += 8.0  # Identifiable gap vs peers
                    verified_issues.append(f"Digital performance lags behind local competitor average by {round(avg_comp_seo - target_seo, 1)} SEO points.")
                else:
                    dpg_score += 4.0
        else:
            dpg_score += 7.5
    else:
        dpg_score += 7.5

    # If website is missing or inaccessible, the gap is high
    if website_analysis and not website_analysis.get("available"):
        dpg_score = max(dpg_score, 12.0)

    cat_scores["digital_presence_gaps"] = min(w["digital_presence_gaps"], round(dpg_score, 1))

    # Category 7: Business Relevance (10 pts)
    # Criteria: Clear industry classification and identifiable location/address.
    br_score = 5.0
    if business_category and business_category.strip():
        br_score += 3.0
    if contact_info and (contact_info.get("address") or contact_info.get("city")):
        br_score += 2.0
    cat_scores["business_relevance"] = min(w["business_relevance"], round(br_score, 1))

    # Total Overall Score
    raw_total = sum(cat_scores.values())
    overall_score = round(max(0.0, min(100.0, raw_total)), 1)

    # Priority Classification
    if overall_score >= 80.0:
        priority_classification = "High Priority"
    elif overall_score >= 60.0:
        priority_classification = "Good Prospect"
    elif overall_score >= 40.0:
        priority_classification = "Medium Priority"
    else:
        priority_classification = "Low Priority"

    # -------------------------------------------------------------
    # 3. Opportunity Scoring (0-100 each for agency services)
    # -------------------------------------------------------------
    # Website Development: High opportunity if website is missing, slow, not mobile-ready, or insecure
    web_dev_opp = 0.0
    if not website_analysis or not website_analysis.get("available"):
        web_dev_opp = 95.0
    else:
        if not website_analysis.get("metadata", {}).get("has_mobile_viewport"):
            web_dev_opp += 35.0
        if not website_analysis.get("protocol", {}).get("is_https"):
            web_dev_opp += 25.0
        if not website_analysis.get("contact_detection", {}).get("has_contact_form"):
            web_dev_opp += 20.0
        if (website_analysis.get("response_time_seconds") or 0) > 2.0:
            web_dev_opp += 20.0
    web_dev_opp = min(100.0, web_dev_opp)

    # SEO Improvement: Inversely related to on-page SEO score
    seo_opp = 0.0
    if seo_audit and "seo_score" in seo_audit:
        seo_opp = max(0.0, 100.0 - float(seo_audit["seo_score"]))
    else:
        seo_opp = 50.0  # Moderate default opportunity if uninspected

    # Social Media Management: High opportunity if social presence is sparse
    if total_social_found == 0:
        social_opp = 90.0
    elif total_social_found == 1:
        social_opp = 70.0
    elif total_social_found == 2:
        social_opp = 40.0
    else:
        social_opp = 15.0

    # Digital Marketing: Opportunity combining contact funnels and competitor gaps
    marketing_opp = 0.0
    if not has_form:
        marketing_opp += 30.0
    if total_social_found < 2:
        marketing_opp += 30.0
    if seo_opp > 40.0:
        marketing_opp += 40.0
    marketing_opp = min(100.0, marketing_opp)

    service_opportunities = {
        "website_development": round(web_dev_opp, 1),
        "seo_services": round(seo_opp, 1),
        "social_media_management": round(social_opp, 1),
        "digital_marketing": round(marketing_opp, 1),
    }

    # -------------------------------------------------------------
    # 4. Recommended Service Package Selection
    # -------------------------------------------------------------
    # If website is missing or completely unavailable, website development is the foundational prerequisite
    if web_dev_opp >= 90.0:
        recommended_package = "Website Development"
    else:
        high_opps = [k for k, v in service_opportunities.items() if v >= 60.0]
        if len(high_opps) >= 3:
            recommended_package = "Combined Digital Growth Package"
        elif web_dev_opp >= 70.0:
            recommended_package = "Website Development"
        elif seo_opp >= 70.0:
            recommended_package = "SEO Services"
        elif social_opp >= 70.0:
            recommended_package = "Social Media Management"
        elif marketing_opp >= 60.0:
            recommended_package = "Digital Marketing"
        else:
            recommended_package = "Combined Digital Growth Package"

    # Explanation text
    explanation = (
        f"{business_name} scored {overall_score}/100 with a {confidence_level} confidence rating "
        f"({evidence_completeness_pct}% evidence completeness). "
        f"Ranked as a {priority_classification} for digital service offerings. "
        f"Identified {len(verified_issues)} verified areas for improvement, with primary growth potential in "
        f"{recommended_package}."
    )

    return {
        "business_name": business_name,
        "overall_lead_score": overall_score,
        "priority_classification": priority_classification,
        "evidence_completeness_percentage": evidence_completeness_pct,
        "confidence_level": confidence_level,
        "category_scores": cat_scores,
        "verified_issues": verified_issues,
        "missing_information": missing_information,
        "service_opportunities": service_opportunities,
        "recommended_service_package": recommended_package,
        "explanation": explanation,
        "disclaimer": (
            "Lead scoring is deterministic and reflects observable digital gaps. "
            "It does not guarantee commercial budget, purchasing authority, or intent to buy."
        ),
    }
