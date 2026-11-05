"""
Excel export for business lead lists.

Generates a formatted 3-worksheet Excel workbook:
1. All Leads
2. High Website Opportunity (opportunity score >= 50)
3. Data Quality Summary
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import openpyxl
from openpyxl.styles import Font

from ..models.business import Business


def _sanitize(value: Any) -> Any:
    """Prevent spreadsheet formula injection."""
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


# Backwards compatibility alias
sanitize_excel_cell = _sanitize


def _to_business(item: Any) -> Business:
    """Ensure lead item is a Business instance."""
    if isinstance(item, Business):
        return item
    if isinstance(item, dict):
        d = dict(item)
        if "id" not in d:
            d["id"] = "lead_" + str(hash(str(d.get("name", ""))))
        if "name" not in d:
            d["name"] = "Unknown Business"
        try:
            return Business.model_validate(d)
        except Exception:
            valid_fields = {k: v for k, v in d.items() if hasattr(Business, k)}
            return Business(id=d.get("id", "lead_temp"), name=d.get("name", "Unknown"), **valid_fields)
    return Business(id="lead_unknown", name=str(item))


def export_to_excel(
    businesses: Optional[list[Any]] = None,
    output_path: str | Path = "leads.xlsx",
    **kwargs: Any,
) -> str:
    """
    Export business leads to a 3-sheet Excel workbook.

    Worksheets:
    1. All Leads
    2. High Website Opportunity (Score >= 50)
    3. Data Quality Summary
    """
    businesses = [_to_business(b) for b in (businesses or [])]

    wb = openpyxl.Workbook()

    headers = [
        "Business Name", "Category", "Address", "City", "Phone", "Email", "Website",
        "Website Status", "Website Opportunity Score", "Score Explanation",
        "Latitude", "Longitude", "Distance (km)", "Data Confidence", "Source", "Research Timestamp"
    ]

    # Worksheet 1: All Leads
    ws_all = wb.active
    ws_all.title = "All Leads"
    ws_all.append(headers)
    for cell in ws_all[1]:
        cell.font = Font(bold=True)
    ws_all.freeze_panes = "A2"

    # Worksheet 2: High Website Opportunity
    ws_high = wb.create_sheet("High Website Opportunity")
    ws_high.append(headers)
    for cell in ws_high[1]:
        cell.font = Font(bold=True)
    ws_high.freeze_panes = "A2"

    timestamp = datetime.now(timezone.utc).isoformat()

    for b in businesses:
        row = [
            b.name, b.category, b.address, b.city, b.phone, b.email, b.website,
            b.website_status, b.website_opportunity_score, b.website_opportunity_explanation,
            b.latitude, b.longitude, b.distance_km, b.data_confidence, b.source, timestamp
        ]
        sanitized_row = [_sanitize(c) for c in row]
        ws_all.append(sanitized_row)

        if b.website_opportunity_score is not None and b.website_opportunity_score >= 50:
            ws_high.append(sanitized_row)

    # Worksheet 3: Data Quality Summary
    ws_summary = wb.create_sheet("Data Quality Summary")
    ws_summary.append(["Metric", "Count"])
    for cell in ws_summary[1]:
        cell.font = Font(bold=True)

    ws_summary.append(["Total Leads", len(businesses)])
    ws_summary.append(["With Phone Numbers", sum(1 for b in businesses if b.phone)])
    ws_summary.append(["With Email Addresses", sum(1 for b in businesses if b.email)])
    ws_summary.append(["Verified Websites", sum(1 for b in businesses if b.website_status == "website_verified")])
    ws_summary.append(["No Verified Official Website", sum(1 for b in businesses if b.website_status == "website_not_found_after_research")])
    ws_summary.append(["Social Media Presence", sum(1 for b in businesses if b.facebook_url or getattr(b, "instagram_url", None) or b.linkedin_url)])
    ws_summary.append(["Uncertain Information", sum(1 for b in businesses if b.website_status == "website_unverified")])
    ws_summary.append(["Missing Contact Details", sum(1 for b in businesses if not b.phone and not b.email)])

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return str(out_path.absolute())
