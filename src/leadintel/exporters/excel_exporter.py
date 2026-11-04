"""
Advanced Multi-Sheet Excel Exporter for LeadIntel.

Uses OpenPyXL to build publication-grade workbooks with 7 sheets:
1. Dashboard Summary
2. Business Leads
3. Website Audit
4. Competitor Intelligence
5. Lead Scoring
6. AI Insights
7. Outreach

Security:
- Prevents CSV/Excel formula injection (sanitizes `=, +, -, @, \t, \r` prefixes).
- Handles missing or incomplete datasets gracefully.
- Freezes header rows, enables auto-filters, and color-codes priority tiers.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..storage.path_validator import validate_safe_export_path

# Palette
HEADER_BG = "1F4E78"       # Dark Navy
HEADER_FG = "FFFFFF"       # White
ZEBRA_BG = "F9FBFD"        # Light Ice Blue
BORDER_COLOR = "D9D9D9"    # Subtle Gray

# Priority Colors
PRIORITY_COLORS = {
    "High Priority": {"fill": "E2EFDA", "font": "375623"},     # Soft Green
    "Good Prospect": {"fill": "D9E1F2", "font": "203764"},     # Soft Blue
    "Medium Priority": {"fill": "FFF2CC", "font": "7F6000"},   # Soft Yellow
    "Low Priority": {"fill": "FCE4D6", "font": "C65911"},      # Soft Orange/Red
}

DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_excel_cell(val: Any) -> Any:
    """Protect against spreadsheet formula injection."""
    if val is None:
        return ""
    if isinstance(val, (int, float, bool)):
        return val
    raw = str(val)
    if raw.startswith(("\t", "\r")):
        return "'" + raw
    s = raw.strip()
    if s.startswith(("=", "+", "-", "@")):
        return "'" + s
    return s


def _style_headers(ws, headers: list[str]) -> None:
    """Format row 1 with dark navy header, white bold text, and freeze row."""
    font = Font(name="Calibri", size=11, bold=True, color=HEADER_FG)
    fill = PatternFill(start_color=HEADER_BG, end_color=HEADER_BG, fill_type="solid")
    align = Alignment(horizontal="left", vertical="center", wrap_text=True)

    ws.row_dimensions[1].height = 28
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font = font
        cell.fill = fill
        cell.alignment = align

    ws.freeze_panes = "A2"
    if headers:
        max_col_letter = get_column_letter(len(headers))
        ws.auto_filter.ref = f"A1:{max_col_letter}1000"


def _adjust_column_widths(ws) -> None:
    """Autofit columns with comfortable padding."""
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            v = str(cell.value or "")
            if len(v) > max_len:
                max_len = len(v)
        # Clamp between 12 and 45
        ws.column_dimensions[col_letter].width = max(12, min(max_len + 4, 45))


def export_to_excel(
    businesses: Optional[list[dict[str, Any]]] = None,
    website_audits: Optional[list[dict[str, Any]]] = None,
    competitor_data: Optional[list[dict[str, Any]]] = None,
    lead_scores: Optional[list[dict[str, Any]]] = None,
    ai_insights_data: Optional[list[dict[str, Any]]] = None,
    outreach_data: Optional[list[dict[str, Any]]] = None,
    output_path: Optional[str] = None,
) -> str:
    """
    Generate a full-featured 7-sheet Excel workbook.

    Returns:
        Absolute file path where workbook was saved.
    """
    businesses = businesses or []
    website_audits = website_audits or []
    competitor_data = competitor_data or []
    lead_scores = lead_scores or []
    ai_insights_data = ai_insights_data or []
    outreach_data = outreach_data or []

    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    thin_border = Border(
        left=Side(style="thin", color=BORDER_COLOR),
        right=Side(style="thin", color=BORDER_COLOR),
        top=Side(style="thin", color=BORDER_COLOR),
        bottom=Side(style="thin", color=BORDER_COLOR),
    )

    # =========================================================================
    # Sheet 1: Dashboard Summary
    # =========================================================================
    ws_dash = wb.create_sheet(title="Dashboard Summary")
    ws_dash.views.sheetView[0].showGridLines = True

    # Title Banner
    ws_dash.merge_cells("A1:E1")
    title_cell = ws_dash["A1"]
    title_cell.value = "LeadIntel — Business Intelligence Executive Dashboard"
    title_cell.font = Font(name="Calibri", size=16, bold=True, color="FFFFFF")
    title_cell.fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    title_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws_dash.row_dimensions[1].height = 40

    ws_dash["A2"] = f"Generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} | Local-first Open Source Intelligence"
    ws_dash["A2"].font = Font(name="Calibri", size=9, italic=True, color="595959")

    # Metrics computation
    total_leads = len(businesses) or len(lead_scores)
    scores = [s.get("overall_lead_score", 0) for s in lead_scores if s.get("overall_lead_score") is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    high_p = sum(1 for s in lead_scores if s.get("priority_classification") == "High Priority")
    good_p = sum(1 for s in lead_scores if s.get("priority_classification") == "Good Prospect")
    med_p = sum(1 for s in lead_scores if s.get("priority_classification") == "Medium Priority")
    low_p = sum(1 for s in lead_scores if s.get("priority_classification") == "Low Priority")

    summary_metrics = [
        ("Total Leads Analyzed", total_leads),
        ("Average Lead Score", f"{avg_score} / 100"),
        ("High Priority Leads", high_p),
        ("Good Prospects", good_p),
        ("Medium Priority Leads", med_p),
        ("Low Priority Leads", low_p),
    ]

    ws_dash.cell(row=4, column=1, value="Metric").font = Font(bold=True)
    ws_dash.cell(row=4, column=2, value="Value").font = Font(bold=True)
    for idx, (label, val) in enumerate(summary_metrics, start=5):
        c1 = ws_dash.cell(row=idx, column=1, value=label)
        c2 = ws_dash.cell(row=idx, column=2, value=sanitize_excel_cell(val))
        c1.font = Font(name="Calibri", size=10, bold=(idx in (5, 6)))
        c2.font = Font(name="Calibri", size=10, bold=True)
        c1.border = thin_border
        c2.border = thin_border

    # Industry breakdown table
    ws_dash.cell(row=4, column=4, value="Category / Industry").font = Font(bold=True)
    ws_dash.cell(row=4, column=5, value="Lead Count").font = Font(bold=True)

    industry_counts: dict[str, int] = {}
    for b in businesses:
        cat = b.get("category") or "Unclassified"
        industry_counts[cat] = industry_counts.get(cat, 0) + 1

    r_idx = 5
    for cat, cnt in sorted(industry_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        c1 = ws_dash.cell(row=r_idx, column=4, value=sanitize_excel_cell(cat))
        c2 = ws_dash.cell(row=r_idx, column=5, value=cnt)
        c1.border = thin_border
        c2.border = thin_border
        r_idx += 1

    _adjust_column_widths(ws_dash)

    # =========================================================================
    # Sheet 2: Business Leads
    # =========================================================================
    ws_leads = wb.create_sheet(title="Business Leads")
    lead_headers = [
        "Business Name", "Category", "Address", "City", "State", "Country",
        "Phone", "Email", "Website", "Social Profiles", "Data Source"
    ]
    _style_headers(ws_leads, lead_headers)

    for r, b in enumerate(businesses, start=2):
        row_vals = [
            b.get("name"),
            b.get("category"),
            b.get("address"),
            b.get("city"),
            b.get("state"),
            b.get("country"),
            b.get("phone"),
            b.get("email"),
            b.get("website"),
            b.get("social_profiles") or b.get("linkedin_url"),
            b.get("source", "openstreetmap"),
        ]
        for col_idx, val in enumerate(row_vals, start=1):
            cell = ws_leads.cell(row=r, column=col_idx, value=sanitize_excel_cell(val))
            cell.border = thin_border
            if col_idx == 9 and val and str(val).startswith("http"):
                cell.hyperlink = str(val)
                cell.font = Font(color="0000FF", underline="single")
    _adjust_column_widths(ws_leads)

    # =========================================================================
    # Sheet 3: Website Audit
    # =========================================================================
    ws_audit = wb.create_sheet(title="Website Audit")
    audit_headers = [
        "Business Name", "Website URL", "Available", "HTTPS Secure",
        "Response Time (s)", "Mobile Viewport", "SEO Score", "SEO Issues Found", "Contact Form"
    ]
    _style_headers(ws_audit, audit_headers)

    for r, a in enumerate(website_audits, start=2):
        seo_data = a.get("seo_audit", {})
        proto = a.get("protocol", {})
        meta = a.get("metadata", {})
        cd = a.get("contact_detection", {})
        issues = seo_data.get("issues", [])
        issues_summary = "; ".join([iss.get("message", "") for iss in issues[:3]])

        row_vals = [
            a.get("business_name") or a.get("name"),
            a.get("url"),
            "Yes" if a.get("available") else "No",
            "Yes" if proto.get("is_https") else "No",
            a.get("response_time_seconds"),
            "Yes" if meta.get("has_mobile_viewport") else "No",
            seo_data.get("seo_score") or a.get("seo_score"),
            issues_summary or "None detected",
            "Yes" if cd.get("has_contact_form") else "No",
        ]
        for col_idx, val in enumerate(row_vals, start=1):
            cell = ws_audit.cell(row=r, column=col_idx, value=sanitize_excel_cell(val))
            cell.border = thin_border
            if col_idx == 2 and val and str(val).startswith("http"):
                cell.hyperlink = str(val)
                cell.font = Font(color="0000FF", underline="single")
    _adjust_column_widths(ws_audit)

    # =========================================================================
    # Sheet 4: Competitor Intelligence
    # =========================================================================
    ws_comp = wb.create_sheet(title="Competitor Intelligence")
    comp_headers = [
        "Target Business", "Competitor Name", "Category", "Website",
        "Competitor Type", "Confidence Score", "SEO Score", "Social Presence"
    ]
    _style_headers(ws_comp, comp_headers)

    r = 2
    for c_group in competitor_data:
        target_name = c_group.get("target_business", {}).get("name") or c_group.get("target_name") or "Target"
        comps = c_group.get("competitors", [])
        for comp in comps:
            dig = comp.get("digital_presence", {})
            row_vals = [
                target_name,
                comp.get("name"),
                comp.get("category"),
                comp.get("website") or dig.get("website"),
                comp.get("competitor_type", "indirect").capitalize(),
                comp.get("confidence_score"),
                dig.get("seo_score", "N/A"),
                f"{dig.get('social_links_count', 0)} channel(s)",
            ]
            for col_idx, val in enumerate(row_vals, start=1):
                cell = ws_comp.cell(row=r, column=col_idx, value=sanitize_excel_cell(val))
                cell.border = thin_border
            r += 1
    _adjust_column_widths(ws_comp)

    # =========================================================================
    # Sheet 5: Lead Scoring
    # =========================================================================
    ws_score = wb.create_sheet(title="Lead Scoring")
    score_headers = [
        "Business Name", "Overall Score", "Priority Tier", "Evidence Completeness",
        "Confidence Level", "Recommended Package", "Verified Issues", "Missing Information"
    ]
    _style_headers(ws_score, score_headers)

    for r, s in enumerate(lead_scores, start=2):
        p_tier = s.get("priority_classification", "Low Priority")
        row_vals = [
            s.get("business_name"),
            s.get("overall_lead_score"),
            p_tier,
            f"{s.get('evidence_completeness_percentage', 0)}%",
            s.get("confidence_level"),
            s.get("recommended_service_package"),
            "; ".join(s.get("verified_issues", [])[:3]),
            "; ".join(s.get("missing_information", [])[:3]),
        ]
        for col_idx, val in enumerate(row_vals, start=1):
            cell = ws_score.cell(row=r, column=col_idx, value=sanitize_excel_cell(val))
            cell.border = thin_border

            # Color code Priority Tier
            if col_idx == 3 and p_tier in PRIORITY_COLORS:
                cfg = PRIORITY_COLORS[p_tier]
                cell.fill = PatternFill(start_color=cfg["fill"], end_color=cfg["fill"], fill_type="solid")
                cell.font = Font(color=cfg["font"], bold=True)
    _adjust_column_widths(ws_score)

    # =========================================================================
    # Sheet 6: AI Insights
    # =========================================================================
    ws_ai = wb.create_sheet(title="AI Insights")
    ai_headers = [
        "Business Name", "AI Model", "Executive Summary", "Opportunity Explanation",
        "Recommended Priorities"
    ]
    _style_headers(ws_ai, ai_headers)

    for r, ai in enumerate(ai_insights_data, start=2):
        ins = ai.get("ai_insights", {})
        recs = ins.get("service_recommendations", [])
        recs_str = "; ".join([f"{item.get('service')} ({item.get('priority')})" for item in recs]) if recs else "N/A"

        row_vals = [
            ai.get("business_name"),
            ai.get("ai_model_used", "Local Ollama"),
            ins.get("executive_summary") or ai.get("summary"),
            ins.get("opportunity_explanation") or ai.get("opportunity"),
            recs_str,
        ]
        for col_idx, val in enumerate(row_vals, start=1):
            cell = ws_ai.cell(row=r, column=col_idx, value=sanitize_excel_cell(val))
            cell.border = thin_border
    _adjust_column_widths(ws_ai)

    # =========================================================================
    # Sheet 7: Outreach
    # =========================================================================
    ws_outreach = wb.create_sheet(title="Outreach")
    outreach_headers = [
        "Business Name", "Email Subject", "Email Body Draft",
        "LinkedIn Connection Message", "WhatsApp Message Draft"
    ]
    _style_headers(ws_outreach, outreach_headers)

    for r, o in enumerate(outreach_data, start=2):
        camp = o.get("outreach_campaign", {})
        em = camp.get("email_pitch", {})
        li = camp.get("linkedin_message", {})
        wa = camp.get("whatsapp_message", {})

        row_vals = [
            o.get("business_name"),
            em.get("subject"),
            em.get("body"),
            li.get("message"),
            wa.get("message"),
        ]
        for col_idx, val in enumerate(row_vals, start=1):
            cell = ws_outreach.cell(row=r, column=col_idx, value=sanitize_excel_cell(val))
            cell.border = thin_border
    _adjust_column_widths(ws_outreach)

    # Save to path
    if not output_path:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_path = validate_safe_export_path(f"leadintel_export_{ts}.xlsx", allowed_extensions={"xlsx"})
    else:
        safe_path = validate_safe_export_path(output_path, allowed_extensions={"xlsx"})

    os.makedirs(os.path.dirname(safe_path) or ".", exist_ok=True)
    wb.save(safe_path)
    return safe_path
