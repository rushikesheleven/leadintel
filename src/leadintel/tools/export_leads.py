"""MCP tool: export_leads — search + export to CSV, JSON, or Excel."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from typing import Literal, Optional

from mcp.server.mcpserver import MCPServer

from ..config import settings
from ..exporters.csv_exporter import export_to_csv
from ..exporters.excel_exporter import export_to_excel
from ..providers import build_registry
from ..storage.path_validator import validate_safe_export_path

OSM_ATTRIBUTION = "Data © OpenStreetMap contributors, ODbL 1.0 — https://www.openstreetmap.org/copyright"

_registry = build_registry(settings)


def register(mcp: MCPServer) -> None:
    """Register export_leads tool on the MCP server."""

    @mcp.tool()
    async def export_leads(
        query: str,
        location: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
        format: Literal["csv", "json", "excel", "xlsx"] = "csv",
        output_path: Optional[str] = None,
    ) -> dict:
        """
        Search for businesses and export results to an Excel (.xlsx), CSV, or JSON file.

        Features:
        - Excel: Creates a multi-sheet workbook with frozen headers, auto-filters, and clean styling.
        - CSV: Standard tabular spreadsheet export.
        - JSON: Complete structured lead metadata with timestamps and attribution.

        Args:
            query: Free-text search term (e.g. 'cafe', 'software').
            location: City, region, or coordinates.
            category: Industry or category filter.
            limit: Max number of leads to export (1-200, default 50).
            format: 'excel' (or 'xlsx'), 'csv' (default), or 'json'.
            output_path: Destination file path (optional).

        Returns:
            Dict containing output_path, row_count, format, and data attribution.
        """
        limit = max(1, min(limit, 200))

        businesses, provider_name = await _registry.search(
            query=query,
            location=location,
            category=category,
            limit=limit,
        )

        is_osm = provider_name == "openstreetmap"
        fmt = format.lower()
        if fmt in ("excel", "xlsx"):
            ext = "xlsx"
        elif fmt == "json":
            ext = "json"
        else:
            ext = "csv"

        if not output_path:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            fname = f"leadintel_export_{ts}.{ext}"
            output_path = os.path.join(tempfile.gettempdir(), fname)

        # Execute export
        if ext == "xlsx":
            biz_dicts = [b.model_dump() for b in businesses]
            abs_path = export_to_excel(businesses=biz_dicts, output_path=output_path)
        elif ext == "json":
            abs_path = _write_json(businesses, output_path, provider_name)
        else:
            abs_path = export_to_csv(businesses, output_path=output_path)

        return {
            "output_path": abs_path,
            "row_count": len(businesses),
            "format": ext,
            "provider": provider_name,
            "attribution": OSM_ATTRIBUTION if is_osm else None,
            "note": (
                f"Exported {len(businesses)} leads to {ext.upper()}. "
                + (f"Attribution: {OSM_ATTRIBUTION}" if is_osm else "")
            ).strip(),
        }


def _write_json(businesses, output_path: str, provider_name: str) -> str:
    safe_path = validate_safe_export_path(output_path, allowed_extensions={"json"})
    os.makedirs(os.path.dirname(safe_path) or ".", exist_ok=True)
    payload = {
        "leadintel_export": True,
        "provider": provider_name,
        "attribution": OSM_ATTRIBUTION if provider_name == "openstreetmap" else None,
        "exported_at": datetime.utcnow().isoformat(),
        "count": len(businesses),
        "businesses": [b.model_dump(mode="json") for b in businesses],
    }
    with open(safe_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return safe_path
