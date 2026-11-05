"""CSV export for business lead lists."""

from __future__ import annotations

import csv
import io
import os
from datetime import datetime
from typing import Any, Optional

from ..models.business import Business
from ..storage.path_validator import validate_safe_export_path

# Columns written to CSV (in order)
_COLUMNS = [
    "id",
    "name",
    "category",
    "address",
    "city",
    "state",
    "country",
    "postal_code",
    "phone",
    "email",
    "website",
    "website_status",
    "website_opportunity_score",
    "detected_cms",
    "has_contact_route",
    "distance_km",
    "linkedin_url",
    "twitter_url",
    "facebook_url",
    "rating",
    "review_count",
    "employee_count_estimate",
    "source",
    "retrieved_at",
    "is_ai_generated",
]

DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(val: Any) -> Any:
    """
    Protect against CSV/spreadsheet formula injection.
    Prefixes values starting with '=', '+', '-', '@', '\\t', '\\r' with a single quote.
    """
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


def _business_to_row(biz: Business) -> dict:
    """Convert a Business model to a flat, sanitized CSV-safe dict."""
    data = biz.model_dump()
    # Flatten datetime
    data["retrieved_at"] = (
        data["retrieved_at"].isoformat()
        if isinstance(data["retrieved_at"], datetime)
        else data["retrieved_at"]
    )
    # Drop geo fields (not useful in a spreadsheet view)
    data.pop("latitude", None)
    data.pop("longitude", None)
    return {col: sanitize_csv_cell(data.get(col, "")) for col in _COLUMNS}


def export_to_csv(
    businesses: list[Business],
    output_path: Optional[str] = None,
) -> str:
    """
    Serialise a list of Business objects to CSV.

    Args:
        businesses: List of Business instances to export.
        output_path: If provided, safely validate and write to this file path and return the path.
                     If None, return the CSV content as a string.

    Returns:
        Absolute file path (when output_path is given) or raw CSV string.

    Raises:
        SecurityValidationError: If output_path violates path safety rules.
        OSError: If writing to output_path fails.
    """
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for biz in businesses:
        writer.writerow(_business_to_row(biz))

    csv_content = buf.getvalue()

    if output_path:
        safe_path = validate_safe_export_path(output_path, allowed_extensions={"csv"})
        os.makedirs(os.path.dirname(safe_path) or ".", exist_ok=True)
        with open(safe_path, "w", newline="", encoding="utf-8") as f:
            f.write(csv_content)
        return safe_path

    return csv_content
