"""
Business Report Generation Service.

Synthesizes technical audits, SEO evaluations, social presence scans, competitor benchmarks,
lead scores, and optional AI strategic observations into comprehensive multi-section business intelligence reports.

Outputs in Markdown, HTML, or structured JSON across 12 mandated sections:
1. Executive Summary
2. Business Overview
3. Digital Presence Assessment
4. Website Technical Audit
5. SEO Analysis
6. Social Media Analysis
7. Competitor Benchmarking
8. Lead Qualification
9. Identified Digital Opportunities
10. Recommended Services
11. Suggested Outreach
12. Data Sources and Limitations
"""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Literal, Optional

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>LeadIntel Business Intelligence Report: {business_name}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #24292e; max-width: 900px; margin: 40px auto; padding: 0 20px; }}
        h1 {{ color: #1f4e78; border-bottom: 2px solid #e1e4e8; padding-bottom: 12px; }}
        h2 {{ color: #2f5597; margin-top: 32px; border-bottom: 1px solid #eaecef; padding-bottom: 6px; }}
        h3 {{ color: #333; }}
        table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
        th, td {{ border: 1px solid #dfe2e5; padding: 10px 12px; text-align: left; }}
        th {{ background-color: #f6f8fa; font-weight: 600; }}
        tr:nth-child(even) {{ background-color: #fafbfc; }}
        .badge {{ display: inline-block; padding: 4px 10px; font-size: 12px; font-weight: bold; border-radius: 4px; }}
        .badge-high {{ background-color: #e2efda; color: #375623; }}
        .badge-good {{ background-color: #d9e1f2; color: #203764; }}
        .badge-med {{ background-color: #fff2cc; color: #7f6000; }}
        .badge-low {{ background-color: #fce4d6; color: #c65911; }}
        .callout {{ background: #f1f8ff; border-left: 4px solid #0366d6; padding: 12px 16px; margin: 16px 0; }}
        .warning {{ background: #fffbdd; border-left: 4px solid #d99b00; padding: 12px 16px; margin: 16px 0; }}
    </style>
</head>
<body>
{body_content}
</body>
</html>
"""


def generate_comprehensive_business_report(
    business_info: dict[str, Any],
    website_analysis: Optional[dict[str, Any]] = None,
    seo_audit: Optional[dict[str, Any]] = None,
    social_profiles: Optional[dict[str, Any]] = None,
    competitor_research: Optional[dict[str, Any]] = None,
    lead_score_data: Optional[dict[str, Any]] = None,
    ai_insights: Optional[dict[str, Any]] = None,
    output_format: Literal["markdown", "html", "json"] = "markdown",
) -> str | dict[str, Any]:
    """
    Generate an executive business intelligence report across 12 structured sections.
    """
    name = business_info.get("name") or "Unknown Business"
    category = business_info.get("category") or "Unclassified"
    city = business_info.get("city") or "Unspecified"
    website = business_info.get("website")
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Extract score details
    score_val = lead_score_data.get("overall_lead_score", 0.0) if lead_score_data else 0.0
    tier = lead_score_data.get("priority_classification", "Unscored") if lead_score_data else "Unscored"
    rec_package = lead_score_data.get("recommended_service_package", "Digital Growth Consultation") if lead_score_data else "General Assessment"

    # Extract SEO
    seo_score = seo_audit.get("seo_score", 0) if seo_audit else "Not Audited"
    seo_issues = [iss.get("message") for iss in seo_audit.get("issues", [])] if seo_audit else []

    # Extract competitors
    comps = competitor_research.get("competitors", []) if competitor_research else []

    # Extract social
    social_dict = social_profiles.get("profiles", social_profiles) if social_profiles else {}
    active_social = [plat.capitalize() for plat, lst in social_dict.items() if isinstance(lst, list) and len(lst) > 0]

    # JSON output
    if output_format.lower() == "json":
        return {
            "report_title": f"Business Intelligence Report: {name}",
            "generated_at": ts,
            "section_1_executive_summary": (
                f"{name} operates in the {category} sector ({city}). Overall prospect score: {score_val}/100 ({tier}). "
                f"Primary recommended engagement: {rec_package}."
            ),
            "section_2_business_overview": {
                "name": name,
                "category": category,
                "city": city,
                "website": website,
                "phone": business_info.get("phone"),
                "email": business_info.get("email"),
            },
            "section_3_digital_presence_assessment": {
                "website_active": website_analysis.get("available", False) if website_analysis else False,
                "https_secure": website_analysis.get("protocol", {}).get("is_https", False) if website_analysis else False,
                "mobile_ready": website_analysis.get("metadata", {}).get("has_mobile_viewport", False) if website_analysis else False,
                "active_social_channels": active_social,
            },
            "section_4_website_technical_audit": website_analysis or {"status": "Not Audited"},
            "section_5_seo_analysis": seo_audit or {"status": "Not Audited"},
            "section_6_social_media_analysis": social_dict,
            "section_7_competitor_benchmarking": comps,
            "section_8_lead_qualification": lead_score_data or {"status": "Not Scored"},
            "section_9_identified_digital_opportunities": lead_score_data.get("service_opportunities") if lead_score_data else {},
            "section_10_recommended_services": rec_package,
            "section_11_suggested_outreach": ai_insights.get("outreach_campaign") if ai_insights and "outreach_campaign" in ai_insights else {},
            "section_12_data_sources_and_limitations": {
                "primary_source": business_info.get("source", "OpenStreetMap / Public Web"),
                "attribution": "Data © OpenStreetMap contributors, ODbL 1.0 (where applicable).",
                "limitations": "Analysis based on publicly observable on-page technical data. No internal access or private information scraped.",
            },
        }

    # Markdown output builder
    md_lines = [
        f"# LeadIntel Intelligence Report: {name}",
        f"**Date Generated:** {ts} | **Source:** {business_info.get('source', 'OpenStreetMap / Public Web')}",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        f"**{name}** is a business in the **{category}** industry located in **{city}**.",
        f"- **Prospect Score:** `{score_val}/100` ({tier})",
        f"- **Recommended Engagement Package:** `{rec_package}`",
        f"- **Primary Finding:** {ai_insights.get('ai_insights', {}).get('executive_summary', 'Established local footprint with identifiable opportunities for digital expansion.') if ai_insights else 'Observable technical gaps present immediate upside for web and search optimizations.'}",
        "",
        "## 2. Business Overview",
        "| Attribute | Value |",
        "|---|---|",
        f"| **Business Name** | {name} |",
        f"| **Category** | {category} |",
        f"| **Location** | {city}, {business_info.get('state', '')} {business_info.get('country', '')} |",
        f"| **Website** | {f'[{website}]({website})' if website else 'Not specified'} |",
        f"| **Phone** | {business_info.get('phone') or 'Not listed'} |",
        f"| **Email** | {business_info.get('email') or 'Not listed'} |",
        "",
        "## 3. Digital Presence Assessment",
        f"- **Website Accessibility:** {'✅ Online & Active' if website_analysis and website_analysis.get('available') else '⚠️ Inactive / No Website'}",
        f"- **HTTPS Security:** {'✅ Secured over HTTPS' if website_analysis and website_analysis.get('protocol', {}).get('is_https') else '⚠️ Insecure / Lacks SSL'}",
        f"- **Mobile Viewport:** {'✅ Mobile Responsive' if website_analysis and website_analysis.get('metadata', {}).get('has_mobile_viewport') else '⚠️ Lacks Mobile Viewport'}",
        f"- **Social Channels:** {', '.join(active_social) if active_social else 'No active social links detected'}",
        "",
        "## 4. Website Technical Audit",
    ]

    if website_analysis and website_analysis.get("available"):
        meta = website_analysis.get("metadata", {})
        resp_t = website_analysis.get("response_time_seconds", "N/A")
        cd = website_analysis.get("contact_detection", {})
        md_lines.extend([
            f"- **Title Tag:** `{meta.get('title') or 'Missing'}`",
            f"- **Meta Description:** `{meta.get('meta_description') or 'Missing'}`",
            f"- **Response Time:** `{resp_t}s`",
            f"- **Contact Form:** {'Detected' if cd.get('has_contact_form') else 'Not detected'}",
        ])
    else:
        md_lines.append("*Website was not analyzed or is unreachable.*")

    md_lines.extend([
        "",
        "## 5. SEO Analysis",
        f"- **Technical SEO Score:** `{seo_score}/100`",
    ])
    if seo_issues:
        md_lines.append("- **Key Detected SEO Issues:**")
        for iss in seo_issues[:5]:
            md_lines.append(f"  - {iss}")
    else:
        md_lines.append("- *No critical SEO issues flagged.*")

    md_lines.extend([
        "",
        "## 6. Social Media Analysis",
        f"- **Active Channels:** {len(active_social)} platform(s)",
        f"- **Profiles Detected:** {', '.join(active_social) if active_social else 'None'}",
        "",
        "## 7. Competitor Benchmarking",
    ])

    if comps:
        md_lines.extend([
            "| Competitor | Type | Category | Website | Confidence |",
            "|---|---|---|---|---|",
        ])
        for c in comps[:5]:
            w_disp = f"[Link]({c.get('website')})" if c.get('website') else "None"
            md_lines.append(
                f"| {c.get('name')} | {c.get('competitor_type', 'indirect').capitalize()} | {c.get('category') or 'N/A'} | {w_disp} | {c.get('confidence_score')} |"
            )
    else:
        md_lines.append("*No local direct competitors benchmarked.*")

    md_lines.extend([
        "",
        "## 8. Lead Qualification",
        f"- **Composite Score:** `{score_val}/100`",
        f"- **Priority Classification:** `{tier}`",
        f"- **Evidence Completeness:** `{lead_score_data.get('evidence_completeness_percentage', 0) if lead_score_data else 0}%`",
        f"- **Confidence Level:** `{lead_score_data.get('confidence_level', 'Unrated') if lead_score_data else 'Unrated'}`",
        "",
        "## 9. Identified Digital Opportunities",
    ])

    if lead_score_data and "service_opportunities" in lead_score_data:
        opps = lead_score_data["service_opportunities"]
        for svc, val in opps.items():
            md_lines.append(f"- **{svc.replace('_', ' ').title()}:** Opportunity Score `{val}/100`")
    else:
        md_lines.append("- *Opportunities not scored.*")

    md_lines.extend([
        "",
        "## 10. Recommended Services",
        f"- **Primary Package:** **{rec_package}**",
        "- **Strategic Rationale:** Tailored to close observable gaps in website performance, technical search visibility, and mobile conversion.",
        "",
        "## 11. Suggested Outreach",
    ])

    # Outreach drafts
    outreach = ai_insights.get("outreach_campaign") if ai_insights else None
    if outreach:
        em = outreach.get("email_pitch", {})
        li = outreach.get("linkedin_message", {})
        wa = outreach.get("whatsapp_message", {})
        md_lines.extend([
            "### Email Draft",
            f"**Subject:** {em.get('subject', 'Partnership inquiry')}",
            "",
            f"{em.get('body', '')}",
            "",
            "### LinkedIn Connection Message",
            f"> {li.get('message', '')}",
            "",
            "### WhatsApp Message Draft",
            f"> {wa.get('message', '')}",
        ])
    else:
        md_lines.extend([
            f"**Suggested Topic:** Introduce your agency's {rec_package} capabilities referencing the verified technical gaps noted in Section 4.",
            "> *Tip: Use the `generate_outreach` tool with local Ollama to produce multi-channel drafts.*",
        ])

    md_lines.extend([
        "",
        "## 12. Data Sources and Limitations",
        "- **Data Sources:** OpenStreetMap (ODbL 1.0 license), direct public HTTP inspection, local deterministic heuristic algorithms.",
        "- **Attribution:** Data © OpenStreetMap contributors, ODbL 1.0 (where applicable).",
        "- **Notice & Transparency:** This report is based exclusively on publicly observable on-page technical data. Lead scoring is deterministic and reflects observable digital gaps. It does not speculate on commercial budgets or purchasing intent.",
    ])

    md_content = "\n".join(md_lines)

    if output_format.lower() == "html":
        # Convert simple markdown headers and tables to basic HTML with HTML-escaping to prevent XSS
        html_body = []
        for line in md_lines:
            if line.startswith("# "):
                html_body.append(f"<h1>{html.escape(line[2:])}</h1>")
            elif line.startswith("## "):
                html_body.append(f"<h2>{html.escape(line[3:])}</h2>")
            elif line.startswith("### "):
                html_body.append(f"<h3>{html.escape(line[4:])}</h3>")
            elif line.startswith("> "):
                html_body.append(f"<blockquote>{html.escape(line[2:])}</blockquote>")
            elif line.startswith("- "):
                html_body.append(f"<li>{html.escape(line[2:])}</li>")
            elif line.startswith("|") and not line.startswith("|---"):
                parts = [f"<td>{html.escape(p.strip())}</td>" for p in line.strip("|").split("|")]
                html_body.append(f"<tr>{''.join(parts)}</tr>")
            elif line.strip() == "---":
                html_body.append("<hr>")
            elif line.strip():
                html_body.append(f"<p>{html.escape(line)}</p>")
        return HTML_TEMPLATE.format(business_name=html.escape(name), body_content="\n".join(html_body))

    return md_content
