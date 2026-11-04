"""
Business Comparison Service.

Compares a target business against one or more competitor businesses across:
- Website availability & response performance
- Technical SEO score (0-100)
- Mobile readiness (viewport configuration)
- Security (HTTPS & valid SSL)
- Social media footprint (channels active)
- Contact accessibility (emails, phone numbers, contact forms)
- Public metrics (ratings and reviews when available)

Generates:
- Structured side-by-side comparison matrix
- Concrete competitive strengths and weaknesses
- High-impact digital opportunities
- Actionable executive positioning summary
"""

from __future__ import annotations

import logging
from typing import Any

from .seo_auditor import run_full_seo_audit
from .website_analyzer import analyze_target_website

logger = logging.getLogger(__name__)


async def _inspect_business_digital_profile(biz_data: dict[str, Any]) -> dict[str, Any]:
    """Inspect or pull digital intelligence for a single business entity."""
    name = biz_data.get("name") or "Unknown"
    website = biz_data.get("website")

    profile: dict[str, Any] = {
        "name": name,
        "website": website,
        "category": biz_data.get("category"),
        "city": biz_data.get("city"),
        "is_https": False,
        "website_available": False,
        "response_time_seconds": None,
        "seo_score": 0,
        "mobile_ready": False,
        "social_channels_count": 0,
        "social_channels": [],
        "has_contact_form": False,
        "has_phone": bool(biz_data.get("phone")),
        "has_email": bool(biz_data.get("email")),
        "rating": biz_data.get("rating"),
        "review_count": biz_data.get("review_count"),
        "status": "no_website" if not website else "analyzed",
    }

    if not website:
        return profile

    # Run website analysis
    try:
        web_res = await analyze_target_website(website, check_broken_links=False)
        if web_res.get("available"):
            profile["website_available"] = True
            profile["is_https"] = web_res.get("protocol", {}).get("is_https", False)
            profile["response_time_seconds"] = web_res.get("response_time_seconds")
            profile["mobile_ready"] = web_res.get("metadata", {}).get("has_mobile_viewport", False)
            profile["has_contact_form"] = web_res.get("contact_detection", {}).get("has_contact_form", False)

            if web_res.get("contact_detection", {}).get("emails_found"):
                profile["has_email"] = True
            if web_res.get("contact_detection", {}).get("phones_found"):
                profile["has_phone"] = True

            # Social channels
            channels = []
            for plat, plist in web_res.get("social_profiles", {}).items():
                if plist:
                    channels.append(plat.capitalize())
            profile["social_channels"] = sorted(channels)
            profile["social_channels_count"] = len(channels)
        else:
            profile["status"] = "inaccessible_website"
            profile["error"] = web_res.get("error", "Website unreachable")
    except Exception as e:
        profile["status"] = "error"
        profile["error"] = str(e)

    # Run SEO audit if website was reachable
    if profile["website_available"]:
        try:
            seo_res = await run_full_seo_audit(website)
            profile["seo_score"] = seo_res.get("seo_score", 0)
        except Exception:
            profile["seo_score"] = 0

    return profile


async def compare_target_against_competitors(
    target_business: dict[str, Any],
    competitors: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Perform a comparative analysis of target_business against a list of competitors.
    """
    if not target_business or not target_business.get("name"):
        raise ValueError("target_business must contain at least a 'name' field.")

    if not competitors:
        return {
            "target_business": target_business.get("name"),
            "competitors_compared_count": 0,
            "comparison_matrix": [],
            "strengths": ["No local competitors identified in this category."],
            "weaknesses": [],
            "opportunities": ["First-mover advantage: expand local presence and claim digital listings."],
            "competitive_positioning_summary": f"{target_business.get('name')} has no immediate competitors identified in the provided list.",
        }

    # Analyze target and competitors
    target_profile = await _inspect_business_digital_profile(target_business)
    competitor_profiles = []
    for comp in competitors:
        comp_profile = await _inspect_business_digital_profile(comp)
        competitor_profiles.append(comp_profile)

    # Compile Comparison Matrix Rows
    all_profiles = [target_profile] + competitor_profiles
    matrix = []
    for p in all_profiles:
        matrix.append({
            "name": p["name"],
            "role": "Target" if p["name"] == target_profile["name"] else "Competitor",
            "website": p["website"],
            "website_available": "Yes" if p["website_available"] else "No",
            "https_secure": "Yes" if p["is_https"] else "No",
            "seo_score": p["seo_score"],
            "mobile_ready": "Yes" if p["mobile_ready"] else "No",
            "social_channels": ", ".join(p["social_channels"]) if p["social_channels"] else "None",
            "contact_form": "Yes" if p["has_contact_form"] else "No",
            "phone_available": "Yes" if p["has_phone"] else "No",
            "email_available": "Yes" if p["has_email"] else "No",
            "rating": p["rating"] or "N/A",
        })

    # Competitive Assessment Engine (Strengths / Weaknesses / Opportunities)
    strengths: list[str] = []
    weaknesses: list[str] = []
    opportunities: list[str] = []

    # 1. SEO Benchmark
    valid_comp_seo = [cp["seo_score"] for cp in competitor_profiles if cp["seo_score"] > 0]
    avg_comp_seo = (sum(valid_comp_seo) / len(valid_comp_seo)) if valid_comp_seo else 0

    if target_profile["seo_score"] >= 80:
        strengths.append(f"Strong on-page technical SEO score ({target_profile['seo_score']}/100), exceeding competitor average ({round(avg_comp_seo, 1)}/100).")
    elif target_profile["seo_score"] < avg_comp_seo and target_profile["website_available"]:
        weaknesses.append(f"Technical SEO score ({target_profile['seo_score']}/100) lags behind industry rivals (average {round(avg_comp_seo, 1)}/100).")
        opportunities.append("Optimize meta descriptions, canonical links, and H1 tags to close the search visibility gap.")

    # 2. Website & Performance
    if target_profile["website_available"] and not any(cp["website_available"] for cp in competitor_profiles):
        strengths.append("Maintains an active digital web property while several competitors have no online website.")
    elif not target_profile["website_available"]:
        weaknesses.append("Target business lacks an accessible, active website.")
        opportunities.append("Deploy a modern, mobile-responsive landing page to capture organic leads.")

    if target_profile["mobile_ready"]:
        strengths.append("Mobile-responsive viewport implemented for smartphone traffic.")
    elif target_profile["website_available"]:
        weaknesses.append("Missing mobile viewport configuration, harming mobile user experience.")
        opportunities.append("Configure a standard viewport meta tag to capture mobile search traffic.")

    # 3. Security (HTTPS)
    if target_profile["is_https"] and any(not cp["is_https"] and cp["website_available"] for cp in competitor_profiles):
        strengths.append("Fully secured over HTTPS/SSL, outperforming insecure competitor domains.")
    elif not target_profile["is_https"] and target_profile["website_available"]:
        weaknesses.append("Website is not served securely over HTTPS.")
        opportunities.append("Implement free SSL/TLS to boost customer trust and search rank.")

    # 4. Social Media
    comp_social_counts = [cp["social_channels_count"] for cp in competitor_profiles]
    max_comp_social = max(comp_social_counts) if comp_social_counts else 0

    if target_profile["social_channels_count"] >= 3 and target_profile["social_channels_count"] >= max_comp_social:
        strengths.append(f"Diversified social presence across {target_profile['social_channels_count']} channels ({', '.join(target_profile['social_channels'])}).")
    elif target_profile["social_channels_count"] < max_comp_social:
        missing_channels = set()
        for cp in competitor_profiles:
            missing_channels.update(cp["social_channels"])
        missing_from_target = missing_channels.difference(target_profile["social_channels"])
        if missing_from_target:
            weaknesses.append(f"Fewer active social channels than competitors (active: {target_profile['social_channels_count']} vs top competitor: {max_comp_social}).")
            opportunities.append(f"Establish brand profiles on {', '.join(sorted(list(missing_from_target)[:3]))} to engage prospective buyers.")

    # 5. Contact Inbound Funnels
    if target_profile["has_contact_form"] and target_profile["has_email"] and target_profile["has_phone"]:
        strengths.append("Comprehensive contact accessibility: inbound form, email, and direct phone available.")
    else:
        if not target_profile["has_contact_form"] and any(cp["has_contact_form"] for cp in competitor_profiles):
            opportunities.append("Add a direct lead capture / contact form to improve inbound conversion rates.")
        if not target_profile["has_phone"]:
            opportunities.append("Display a verified business phone number for rapid customer inquiries.")

    # Summary Generation
    summary = (
        f"{target_profile['name']} was benchmarked against {len(competitor_profiles)} industry competitors. "
        f"Target SEO Score: {target_profile['seo_score']}/100 (Competitor average: {round(avg_comp_seo, 1)}/100). "
        f"Identified {len(strengths)} key digital strengths and {len(opportunities)} high-leverage growth opportunities."
    )

    return {
        "target_business": target_profile["name"],
        "competitors_compared_count": len(competitor_profiles),
        "comparison_matrix": matrix,
        "strengths": strengths or ["Established baseline presence in the local market."],
        "weaknesses": weaknesses or ["No critical structural weaknesses observed."],
        "opportunities": opportunities or ["Maintain current competitive lead and refresh content regularly."],
        "competitive_positioning_summary": summary,
    }
