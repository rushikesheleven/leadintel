"""
MCP Tool: generate_business_report

Synthesizes complete business intelligence into comprehensive multi-section reports
available in Markdown, HTML, or structured JSON.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from mcp.server.mcpserver import MCPServer

from ..services.business_report import generate_comprehensive_business_report


def register(mcp: MCPServer) -> None:
    """Register generate_business_report tool on the MCP server."""

    @mcp.tool()
    async def generate_business_report(
        business_info: dict[str, Any],
        website_analysis: Optional[dict[str, Any]] = None,
        seo_audit: Optional[dict[str, Any]] = None,
        social_profiles: Optional[dict[str, Any]] = None,
        competitor_research: Optional[dict[str, Any]] = None,
        lead_score_data: Optional[dict[str, Any]] = None,
        ai_insights: Optional[dict[str, Any]] = None,
        output_format: Literal["markdown", "html", "json"] = "markdown",
    ) -> dict[str, Any]:
        """
        Generate a comprehensive 12-section business intelligence report.

        Synthesizes technical audits, SEO evaluations, social presence scans,
        competitor benchmarks, lead scores, and optional AI strategic insights.

        Report Sections:
        1. Executive Summary
        2. Business Overview
        3. Digital Presence Assessment
        4. Website Technical Audit
        5. SEO Analysis
        6. Social Media Analysis
        7. Competitor Benchmarking
        8. Lead Qualification & Scoring
        9. Identified Digital Opportunities
        10. Recommended Service Packages
        11. Suggested Multi-Channel Outreach
        12. Data Sources, Attributions & Limitations

        Features:
        - Works completely offline without AI or external paid APIs.
        - Outputs in Markdown, HTML, or structured JSON.
        - Accurately references OpenStreetMap ODbL attributions.

        Args:
            business_info: Dict containing at least 'name', plus optional 'category', 'city', 'website'.
            website_analysis: Output from analyze_website tool (optional).
            seo_audit: Output from check_seo tool (optional).
            social_profiles: Output from find_social_profiles tool (optional).
            competitor_research: Output from find_competitors tool (optional).
            lead_score_data: Output from score_lead tool (optional).
            ai_insights: Output from generate_business_insights or generate_outreach tool (optional).
            output_format: 'markdown' (default), 'html', or 'json'.

        Returns:
            Dict containing the rendered report content, format, and metadata.
        """
        try:
            report_result = generate_comprehensive_business_report(
                business_info=business_info,
                website_analysis=website_analysis,
                seo_audit=seo_audit,
                social_profiles=social_profiles,
                competitor_research=competitor_research,
                lead_score_data=lead_score_data,
                ai_insights=ai_insights,
                output_format=output_format,
            )

            return {
                "business_name": business_info.get("name"),
                "format": output_format.lower(),
                "report": report_result,
            }
        except Exception as exc:
            return {
                "error": str(exc),
                "business_name": business_info.get("name") if isinstance(business_info, dict) else str(business_info),
                "format": output_format.lower(),
                "report": f"Report generation failed: {exc}",
            }
