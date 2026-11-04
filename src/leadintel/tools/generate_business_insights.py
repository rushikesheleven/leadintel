"""
MCP Tool: generate_business_insights

Generates strategic AI business intelligence and opportunity explanations
using a local Ollama model without external cloud API dependencies.
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.mcpserver import MCPServer

from ..services.ai_business_insights import generate_ai_business_insights
from ..services.local_ai import LocalAIClient, OllamaError, OllamaUnavailableError


def register(mcp: MCPServer) -> None:
    """Register generate_business_insights tool on the MCP server."""

    @mcp.tool()
    async def generate_business_insights(
        business_name: str,
        business_category: Optional[str] = None,
        website_analysis: Optional[dict[str, Any]] = None,
        seo_audit: Optional[dict[str, Any]] = None,
        social_profiles: Optional[dict[str, Any]] = None,
        competitor_comparison: Optional[dict[str, Any]] = None,
        lead_score_data: Optional[dict[str, Any]] = None,
        contact_info: Optional[dict[str, Any]] = None,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Generate evidence-based strategic business insights using local Ollama AI.

        Synthesizes technical audits, competitor benchmarks, and lead scores to provide:
        - Executive summary of digital maturity
        - Clear explanations for digital marketing and SEO opportunities
        - Strategic interpretation of the deterministic lead score
        - Grounded competitor insights
        - Actionable service recommendations (Web Dev, SEO, Social, Marketing)

        Ethical & Operational Safeguards:
        - Connects to local Ollama (http://localhost:11434). Zero cloud AI calls or tokens used.
        - Grounded strictly in provided evidence; never invents revenue, budgets, or purchasing intent.
        - If Ollama is not installed or running, returns a clean informative error without crashing.

        Args:
            business_name: Name of the business (required).
            business_category: Industry/category description.
            website_analysis: Results from analyze_website tool (optional).
            seo_audit: Results from check_seo tool (optional).
            social_profiles: Results from find_social_profiles tool (optional).
            competitor_comparison: Results from compare_businesses tool (optional).
            lead_score_data: Results from score_lead tool (optional).
            contact_info: Available contact details (optional).
            model: Optional Ollama model override (default: configured OLLAMA_MODEL, e.g. 'llama3').

        Returns:
            Structured AI insights grounded in verified facts.
        """
        client = LocalAIClient(model=model) if model else None
        try:
            return await generate_ai_business_insights(
                business_name=business_name,
                business_category=business_category,
                website_analysis=website_analysis,
                seo_audit=seo_audit,
                social_profiles=social_profiles,
                competitor_comparison=competitor_comparison,
                lead_score_data=lead_score_data,
                contact_info=contact_info,
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
                "error": "Ollama generation failed.",
                "message": str(e),
                "business_name": business_name,
            }
        except Exception as exc:
            return {
                "error": "Failed to generate business insights.",
                "message": str(exc),
                "business_name": business_name,
            }
