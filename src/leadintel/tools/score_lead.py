"""
MCP Tool: score_lead

Evaluates and qualifies a business lead for digital service providers
using deterministic, multi-dimensional evidence scoring.
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.mcpserver import MCPServer

from ..services.lead_scoring import score_business_lead


def register(mcp: MCPServer) -> None:
    """Register score_lead tool on the MCP server."""

    @mcp.tool()
    async def score_lead(
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
        Evaluate and score a business lead for digital services suitability.

        Calculates a deterministic 0-100 overall prospect score based on:
        1. Website quality (max 20 pts)
        2. Technical SEO (max 20 pts)
        3. Social media presence (max 15 pts)
        4. Contact accessibility (max 10 pts)
        5. Mobile readiness (max 10 pts)
        6. Digital presence gaps vs competitors (max 15 pts)
        7. Business relevance & localization (max 10 pts)

        Opportunity Analysis:
        Provides specialized opportunity scores (0-100) for:
        - Website Development
        - SEO Services
        - Social Media Management
        - Digital Marketing

        Compliance & Ethics:
        - Missing inputs reduce confidence and evidence completeness, avoiding arbitrary score penalties.
        - Verified defects are separated from missing information.
        - Does not speculate on customer purchasing budget or guarantee conversion.
        - Uses zero paid APIs or tokens.

        Args:
            business_name: Name of the business (required).
            business_category: Industry/category description.
            website_analysis: Results from analyze_website tool (optional).
            seo_audit: Results from check_seo tool (optional).
            social_profiles: Results from find_social_profiles tool (optional).
            competitor_comparison: Results from compare_businesses tool (optional).
            contact_info: Available phone, email, or address dictionary (optional).
            weights: Optional custom weight overrides for the 7 categories.

        Returns:
            Structured lead evaluation report including overall score, priority tier,
            service opportunities, and recommended package.
        """
        try:
            return score_business_lead(
                business_name=business_name,
                business_category=business_category,
                website_analysis=website_analysis,
                seo_audit=seo_audit,
                social_profiles=social_profiles,
                competitor_comparison=competitor_comparison,
                contact_info=contact_info,
                weights=weights,
            )
        except Exception as exc:
            return {
                "error": str(exc),
                "business_name": business_name,
                "overall_lead_score": 0.0,
                "priority_classification": "Low Priority",
                "explanation": f"Lead scoring failed: {exc}",
            }
