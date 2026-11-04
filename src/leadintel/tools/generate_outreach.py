"""
MCP Tool: generate_outreach

Synthesizes tailored, respectful B2B outreach messaging (Email, LinkedIn, WhatsApp)
using local Ollama models grounded in verified technical findings.
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.mcpserver import MCPServer

from ..services.ai_business_insights import generate_ai_outreach
from ..services.local_ai import LocalAIClient, OllamaError, OllamaUnavailableError


def register(mcp: MCPServer) -> None:
    """Register generate_outreach tool on the MCP server."""

    @mcp.tool()
    async def generate_outreach(
        business_name: str,
        business_category: Optional[str] = None,
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

        Args:
            business_name: Target company name (required).
            business_category: Business industry/category.
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
        client = LocalAIClient(model=model) if model else None
        try:
            return await generate_ai_outreach(
                business_name=business_name,
                business_category=business_category,
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
