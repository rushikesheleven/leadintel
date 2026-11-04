"""
Comprehensive Unit Tests for Step 7: Advanced Data Export & Business Report Generation.

Covers:
- Excel workbook generation with all 7 sheets
- Worksheet names and presence validation
- Formula injection protection test
- Handling of missing business information, SEO, competitors, and AI
- Empty datasets export
- Report generation across all 3 formats: Markdown, HTML, JSON
- All 12 report sections presence
- MCP tool execution for generate_business_report and export_leads (Excel format)
"""

from __future__ import annotations

import json
import os
import tempfile

import openpyxl
import pytest

from leadintel.exporters.excel_exporter import export_to_excel, sanitize_excel_cell
from leadintel.server import mcp
from leadintel.services.business_report import generate_comprehensive_business_report

# ── Formula Injection Protection Tests ────────────────────────────────────────

class TestFormulaInjectionProtection:
    def test_sanitizes_equals_prefix(self):
        val = sanitize_excel_cell("=SUM(A1:A10)")
        assert val == "'=SUM(A1:A10)"

    def test_sanitizes_plus_minus_at_prefix(self):
        assert sanitize_excel_cell("+12345").startswith("'+")
        assert sanitize_excel_cell("-cmd|' /C calc'!A0").startswith("'-")
        assert sanitize_excel_cell("@SUM(1,2)").startswith("'@")

    def test_allows_clean_strings_and_numbers(self):
        assert sanitize_excel_cell("Acme Tech") == "Acme Tech"
        assert sanitize_excel_cell(42) == 42
        assert sanitize_excel_cell(99.5) == 99.5
        assert sanitize_excel_cell(True) is True
        assert sanitize_excel_cell(None) == ""


# ── Excel Exporter Tests ──────────────────────────────────────────────────────

class TestExcelExporter:
    def test_generates_all_7_worksheets(self):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            path = f.name

        try:
            sample_leads = [
                {"name": "Acme Tech", "category": "Software", "city": "San Francisco", "website": "https://acme.example"}
            ]
            sample_scores = [
                {"business_name": "Acme Tech", "overall_lead_score": 75.5, "priority_classification": "Good Prospect"}
            ]

            saved_path = export_to_excel(
                businesses=sample_leads,
                lead_scores=sample_scores,
                output_path=path,
            )
            assert os.path.exists(saved_path)

            wb = openpyxl.load_workbook(saved_path)
            sheet_names = wb.sheetnames
            expected_sheets = [
                "Dashboard Summary",
                "Business Leads",
                "Website Audit",
                "Competitor Intelligence",
                "Lead Scoring",
                "AI Insights",
                "Outreach",
            ]
            for s in expected_sheets:
                assert s in sheet_names

            # Verify formula injection sanitization in sheets
            ws_leads = wb["Business Leads"]
            assert ws_leads.cell(row=2, column=1).value == "Acme Tech"

        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_export_empty_datasets_succeeds(self):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            path = f.name
        try:
            saved_path = export_to_excel(output_path=path)
            assert os.path.exists(saved_path)
            wb = openpyxl.load_workbook(saved_path)
            assert "Dashboard Summary" in wb.sheetnames
            assert wb["Dashboard Summary"]["A1"].value is not None
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_export_formula_injection_mitigation_in_file(self):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            path = f.name
        try:
            malicious_lead = {
                "name": "=cmd|' /C calc'!A0",
                "category": "@SUM(1+1)",
                "city": "+12345",
            }
            saved_path = export_to_excel(businesses=[malicious_lead], output_path=path)
            wb = openpyxl.load_workbook(saved_path)
            ws = wb["Business Leads"]
            assert ws.cell(row=2, column=1).value.startswith("'=")
            assert ws.cell(row=2, column=2).value.startswith("'@")
            assert ws.cell(row=2, column=4).value.startswith("'+")
        finally:
            if os.path.exists(path):
                os.unlink(path)


# ── Business Report Generator Tests ───────────────────────────────────────────

class TestBusinessReportGenerator:
    def test_generate_markdown_report_all_12_sections(self):
        biz_info = {
            "name": "Pacific Software",
            "category": "Technology",
            "city": "Seattle",
            "website": "https://pacific.example",
        }
        lead_score = {
            "overall_lead_score": 68.0,
            "priority_classification": "Good Prospect",
            "service_opportunities": {"website_development": 40.0, "seo_services": 80.0},
            "recommended_service_package": "SEO Services",
        }
        report_md = generate_comprehensive_business_report(
            business_info=biz_info,
            lead_score_data=lead_score,
            output_format="markdown",
        )
        assert isinstance(report_md, str)
        # Check presence of all 12 sections
        for sec in range(1, 13):
            assert f"## {sec}." in report_md

        assert "Pacific Software" in report_md
        assert "Good Prospect" in report_md
        assert "OpenStreetMap" in report_md

    def test_generate_html_report(self):
        biz_info = {"name": "Sunrise Cafe", "category": "Food & Beverage"}
        report_html = generate_comprehensive_business_report(
            business_info=biz_info,
            output_format="html",
        )
        assert isinstance(report_html, str)
        assert "<!DOCTYPE html>" in report_html
        assert "Sunrise Cafe" in report_html
        assert "<h1>" in report_html

    def test_generate_json_report(self):
        biz_info = {"name": "Metro Transit Logistics", "category": "Logistics"}
        report_json = generate_comprehensive_business_report(
            business_info=biz_info,
            output_format="json",
        )
        assert isinstance(report_json, dict)
        assert report_json["report_title"] == "Business Intelligence Report: Metro Transit Logistics"
        assert "section_1_executive_summary" in report_json
        assert "section_12_data_sources_and_limitations" in report_json

    def test_report_without_ai_or_seo_works_gracefully(self):
        # Missing SEO, missing competitors, missing AI
        biz_info = {"name": "Bare Bones Co"}
        report_md = generate_comprehensive_business_report(
            business_info=biz_info,
            output_format="markdown",
        )
        assert "Bare Bones Co" in report_md
        assert "Website was not analyzed or is unreachable" in report_md
        assert "No local direct competitors benchmarked" in report_md


# ── MCP Tools Step 7 Execution Tests ──────────────────────────────────────────

@pytest.mark.asyncio
class TestMcpToolsStep7:
    async def test_mcp_generate_business_report(self):
        res = await mcp.call_tool("generate_business_report", {
            "business_info": {
                "name": "Acme Tech Solutions",
                "category": "Software Development",
                "city": "San Francisco",
            },
            "output_format": "markdown",
        })
        content = res.content[0].text if hasattr(res.content[0], "text") else res.content[0]
        data = json.loads(content) if isinstance(content, str) else content

        assert data["business_name"] == "Acme Tech Solutions"
        assert data["format"] == "markdown"
        assert "## 1. Executive Summary" in data["report"]

    async def test_mcp_export_leads_excel_format(self):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            tmp_path = f.name

        try:
            res = await mcp.call_tool("export_leads", {
                "query": "tech",
                "format": "excel",
                "output_path": tmp_path,
            })
            content = res.content[0].text if hasattr(res.content[0], "text") else res.content[0]
            data = json.loads(content) if isinstance(content, str) else content

            assert data["format"] == "xlsx"
            assert os.path.exists(data["output_path"])
            wb = openpyxl.load_workbook(data["output_path"])
            assert "Business Leads" in wb.sheetnames
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
