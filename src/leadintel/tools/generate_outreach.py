"""
MCP Tool: generate_outreach

Synthesizes tailored, respectful B2B outreach messaging (Email, LinkedIn, WhatsApp)
using local Ollama models grounded in verified technical findings and website opportunities.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from mcp.server.mcpserver import MCPServer

from ..models.business import Business
from ..services.ai_business_insights import generate_ai_outreach
from ..services.local_ai import LocalAIClient, OllamaError, OllamaUnavailableError
from ..storage.db import get_business

logger = logging.getLogger(__name__)


def register(mcp: MCPServer) -> None:
    """Register generate_outreach tool on the MCP server."""

    @mcp.tool()
    async def generate_outreach(
        business_name: str,
        business_id: Optional[str] = None,
        business: Optional[dict[str, Any]] = None,
        business_category: Optional[str] = None,
        website_status: Optional[str] = None,
        website_opportunity_score: Optional[float] = None,
        website_opportunity_explanation: Optional[str] = None,
        detected_cms: Optional[str] = None,
        has_contact_route: Optional[bool] = None,
        website_analysis: Optional[dict[str, Any]] = None,
        seo_audit: Optional[dict[str, Any]] = None,
        social_profiles: Optional[dict[str, Any]] = None,
        competitor_comparison: Optional[dict[str, Any]] = None,
        lead_score_data: Optional[dict[str, Any]] = None,
        contact_info: Optional[dict[str, Any]] = None,
        agency_name: str = "Our Agency",
        sender_name: str = "Lead Specialist",
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Generate personalized, multi-channel B2B outreach messages using local Ollama AI.

        Produces ready-to-use drafts across 3 channels:
        - Email pitch: Structured subject line + 3-paragraph value-first pitch referencing verified findings.
        - LinkedIn message: Concise connection request (< 300 characters).
        - WhatsApp Business: Respectful, direct conversational pitch (< 120 words).

        Ethical & Operational Safeguards:
        - Uses local Ollama model (no third-party cloud data transfer).
        - Grounded exclusively in verified technical data.
        - Does not invent fake claims, guarantees, or assume prospect budgets.
        - Strict guardrails: "Do not fabricate business data or website problems. Base the outreach strictly on the provided website_opportunity_explanation. If the site is missing (website_not_found_after_research), pitch a new build. If a CMS is detected or a contact route is missing, mention it as a specific reason for outreach."

        Args:
            business_name: Target company name (required).
            business_id: Optional business ID to automatically retrieve stored business from SQLite.
            business: Optional dictionary representation of a Business instance.
            business_category: Business industry/category.
            website_status: Status of the business website (e.g. 'website_not_found_after_research').
            website_opportunity_score: Deterministic 0–100 score prioritizing website opportunity.
            website_opportunity_explanation: Evidence-based explanation of the website opportunity.
            detected_cms: Detected CMS (WordPress, Shopify, Wix, Squarespace).
            has_contact_route: Boolean indicating presence of contact form/mailto route.
            website_analysis: Results from analyze_website tool (optional).
            seo_audit: Results from check_seo tool (optional).
            social_profiles: Results from find_social_profiles tool (optional).
            competitor_comparison: Results from compare_businesses tool (optional).
            lead_score_data: Results from score_lead tool (optional).
            contact_info: Contact details dictionary (optional).
            agency_name: Your digital agency or company name.
            sender_name: Name of the person/role sending the message.
            model: Optional Ollama model override.

        Returns:
            Dict containing multi-channel outreach drafts.
        """
        # Retrieve or reconstruct Business object if available
        biz_obj: Optional[Business] = None
        if business_id:
            biz_obj = get_business(business_id)
        elif business:
            try:
                biz_obj = Business.model_validate(business)
            except Exception:
                pass
        if not biz_obj and business_name:
            biz_obj = get_business(business_name)

        if biz_obj:
            if not business_category and biz_obj.category:
                business_category = biz_obj.category
            website_status = website_status or biz_obj.website_status
            if website_opportunity_score is None:
                website_opportunity_score = biz_obj.website_opportunity_score
            website_opportunity_explanation = (
                website_opportunity_explanation or biz_obj.website_opportunity_explanation
            )
            detected_cms = detected_cms or biz_obj.detected_cms
            if has_contact_route is None:
                has_contact_route = biz_obj.has_contact_route
            if not contact_info:
                contact_info = {
                    "city": biz_obj.city,
                    "phone": biz_obj.phone,
                    "email": biz_obj.email,
                }

        client = LocalAIClient(model=model) if model else None
        try:
            return await generate_ai_outreach(
                business_name=business_name,
                business_category=business_category,
                website_status=website_status,
                website_opportunity_score=website_opportunity_score,
                website_opportunity_explanation=website_opportunity_explanation,
                detected_cms=detected_cms,
                has_contact_route=has_contact_route,
                website_analysis=website_analysis,
                seo_audit=seo_audit,
                social_profiles=social_profiles,
                competitor_comparison=competitor_comparison,
                lead_score_data=lead_score_data,
                contact_info=contact_info,
                agency_name=agency_name,
                sender_name=sender_name,
                ai_client=client,
            )
        except OllamaUnavailableError as e:
            return {
                "error": "Ollama server is unavailable.",
                "message": str(e),
                "business_name": business_name,
                "suggestion": "Ensure Ollama is installed and running locally with 'ollama serve'.",
            }
        except OllamaError as e:
            return {
                "error": "Ollama outreach generation failed.",
                "message": str(e),
                "business_name": business_name,
            }
        except Exception as exc:
            return {
                "error": "Failed to generate outreach drafts.",
                "message": str(exc),
                "business_name": business_name,
            }
