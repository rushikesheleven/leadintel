"""
AI Business Insights & Outreach Generation Service.

Bridges deterministic LeadIntel intelligence (website analysis, SEO audits, competitor benchmarks, lead scores)
with local Ollama inference.

Strict Ethical Rules:
- NEVER fabricates business revenue, marketing budgets, purchasing intent, or competitor weaknesses.
- Labels all AI-generated synthesis clearly as `is_ai_generated: true` while preserving verified factual sources.
- Grounded strictly in provided evidence: if data is absent, notes it explicitly rather than hallucinating.
- Generates high-impact B2B outreach across Email, LinkedIn, and WhatsApp Business.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from .local_ai import LocalAIClient, local_ai_client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_INSIGHTS = """You are a senior business intelligence and digital strategy analyst.
Your job is to provide objective, evidence-based insights for a business based EXCLUSIVELY on provided verified technical data.

STRICT CONSTRAINTS:
1. NEVER invent or assume company revenue, marketing budget, or customer purchasing intent.
2. Ground all recommendations strictly in observable digital defects and gaps (e.g. missing SSL, slow response, missing H1, poor mobile viewport, lack of social links).
3. Distinguish verified facts from AI strategic interpretations.
4. Output valid JSON when requested.
"""

SYSTEM_PROMPT_OUTREACH = """You are an expert B2B digital agency consultant writing personalized, respectful, and highly specific outreach messages to a business decision maker.

STRICT CONSTRAINTS:
1. Do not use generic buzzwords or clickbait claims.
2. Directly reference 1-2 verified, specific digital findings (e.g., website loading speed, lack of mobile viewport, missing meta descriptions, or competitor gap).
3. Propose a collaborative, value-first conversation without assuming their budget or readiness to buy.
4. Generate three distinct channels: Email Pitch, LinkedIn Message, and WhatsApp Business message.
5. Output valid JSON.
"""


def _build_context_summary(
    business_name: str,
    business_category: Optional[str] = None,
    website_analysis: Optional[dict[str, Any]] = None,
    seo_audit: Optional[dict[str, Any]] = None,
    social_profiles: Optional[dict[str, Any]] = None,
    competitor_comparison: Optional[dict[str, Any]] = None,
    lead_score_data: Optional[dict[str, Any]] = None,
    contact_info: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Compile structured verified facts to ground AI synthesis."""
    verified_facts: dict[str, Any] = {
        "business_name": business_name,
        "category": business_category or "Unspecified",
    }

    if contact_info:
        verified_facts["contact"] = {
            "city": contact_info.get("city"),
            "has_phone": bool(contact_info.get("phone")),
            "has_email": bool(contact_info.get("email")),
        }

    if website_analysis:
        verified_facts["website"] = {
            "url": website_analysis.get("url"),
            "available": website_analysis.get("available"),
            "is_https": website_analysis.get("protocol", {}).get("is_https"),
            "response_time_seconds": website_analysis.get("response_time_seconds"),
            "mobile_viewport_configured": website_analysis.get("metadata", {}).get("has_mobile_viewport"),
            "has_contact_form": website_analysis.get("contact_detection", {}).get("has_contact_form"),
        }

    if seo_audit:
        verified_facts["seo"] = {
            "score": seo_audit.get("seo_score"),
            "issues_sample": [iss.get("message") for iss in seo_audit.get("issues", [])][:4],
        }

    if social_profiles:
        profiles_dict = social_profiles.get("profiles", social_profiles)
        active = [plat for plat, links in profiles_dict.items() if isinstance(links, list) and len(links) > 0]
        verified_facts["social_media"] = {
            "active_channels": active,
            "channel_count": len(active),
        }

    if competitor_comparison:
        verified_facts["competitor_context"] = {
            "competitors_compared": competitor_comparison.get("competitors_compared_count", 0),
            "strengths_sample": competitor_comparison.get("strengths", [])[:2],
            "weaknesses_sample": competitor_comparison.get("weaknesses", [])[:2],
        }

    if lead_score_data:
        verified_facts["lead_score"] = {
            "overall_score": lead_score_data.get("overall_lead_score"),
            "priority": lead_score_data.get("priority_classification"),
            "service_opportunities": lead_score_data.get("service_opportunities"),
            "recommended_package": lead_score_data.get("recommended_service_package"),
            "verified_issues": lead_score_data.get("verified_issues", [])[:5],
        }

    return verified_facts


async def generate_ai_business_insights(
    business_name: str,
    business_category: Optional[str] = None,
    website_analysis: Optional[dict[str, Any]] = None,
    seo_audit: Optional[dict[str, Any]] = None,
    social_profiles: Optional[dict[str, Any]] = None,
    competitor_comparison: Optional[dict[str, Any]] = None,
    lead_score_data: Optional[dict[str, Any]] = None,
    contact_info: Optional[dict[str, Any]] = None,
    ai_client: Optional[LocalAIClient] = None,
    http_client: Optional[httpx.AsyncClient] = None,
) -> dict[str, Any]:
    """
    Generate evidence-based strategic business insights using local Ollama.
    """
    if not business_name or not business_name.strip():
        raise ValueError("business_name must be a non-empty string.")

    client = ai_client or local_ai_client
    verified_data = _build_context_summary(
        business_name=business_name,
        business_category=business_category,
        website_analysis=website_analysis,
        seo_audit=seo_audit,
        social_profiles=social_profiles,
        competitor_comparison=competitor_comparison,
        lead_score_data=lead_score_data,
        contact_info=contact_info,
    )

    prompt = f"""Analyze the verified business data below and produce a structured strategic insight report in JSON format.

VERIFIED DATA:
{json.dumps(verified_data, indent=2)}

Required JSON schema:
{{
  "executive_summary": "string summarizing digital maturity and key findings",
  "opportunity_explanation": "string explaining why specific digital opportunities exist based on the evidence",
  "lead_score_interpretation": "string contextualizing the deterministic lead score without altering it",
  "competitor_insights": "string comparing their posture against market peers",
  "service_recommendations": [
    {{
      "service": "Website Development | SEO | Social Media Management | Digital Marketing",
      "rationale": "specific evidence-backed reason",
      "priority": "High | Medium | Low"
    }}
  ]
}}
"""

    raw_response = await client.generate(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_INSIGHTS,
        format_json=True,
        client=http_client,
    )

    try:
        parsed_insights = json.loads(raw_response)
    except json.JSONDecodeError:
        parsed_insights = {
            "executive_summary": raw_response,
            "opportunity_explanation": "Extracted from local AI response.",
            "lead_score_interpretation": "See deterministic lead score report.",
            "competitor_insights": "Refer to competitor comparison matrix.",
            "service_recommendations": [],
        }

    return {
        "business_name": business_name,
        "is_ai_generated": True,
        "ai_model_used": client.model,
        "verified_facts_grounding": verified_data,
        "ai_insights": parsed_insights,
        "disclaimer": (
            "Observations under 'ai_insights' were synthesized by a local AI model grounded strictly in verified data. "
            "No assumptions regarding customer budget or revenue were made."
        ),
    }


async def generate_ai_outreach(
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
    ai_client: Optional[LocalAIClient] = None,
    http_client: Optional[httpx.AsyncClient] = None,
) -> dict[str, Any]:
    """
    Generate tailored B2B outreach messages across Email, LinkedIn, and WhatsApp Business.
    """
    if not business_name or not business_name.strip():
        raise ValueError("business_name must be a non-empty string.")

    client = ai_client or local_ai_client
    verified_data = _build_context_summary(
        business_name=business_name,
        business_category=business_category,
        website_analysis=website_analysis,
        seo_audit=seo_audit,
        social_profiles=social_profiles,
        competitor_comparison=competitor_comparison,
        lead_score_data=lead_score_data,
        contact_info=contact_info,
    )

    prompt = f"""Generate personalized, professional B2B outreach messages for {business_name} in JSON format.
Sender: {sender_name} representing {agency_name}.

VERIFIED CONTEXT:
{json.dumps(verified_data, indent=2)}

Required JSON schema:
{{
  "email_pitch": {{
    "subject": "Clear, curiosity-inducing subject line",
    "body": "Professional 3-paragraph email referencing 1-2 verified technical findings and a low-friction call-to-action."
  }},
  "linkedin_message": {{
    "message": "Concise connection message (under 300 characters) referencing their business and specific digital insight."
  }},
  "whatsapp_message": {{
    "message": "Polite, direct WhatsApp Business message (under 120 words) with clear value proposition and polite sign-off."
  }}
}}
"""

    raw_response = await client.generate(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT_OUTREACH,
        format_json=True,
        client=http_client,
    )

    try:
        parsed_outreach = json.loads(raw_response)
    except json.JSONDecodeError:
        parsed_outreach = {
            "email_pitch": {"subject": f"Quick thought regarding {business_name}", "body": raw_response},
            "linkedin_message": {"message": raw_response[:280]},
            "whatsapp_message": {"message": raw_response[:300]},
        }

    return {
        "business_name": business_name,
        "is_ai_generated": True,
        "ai_model_used": client.model,
        "outreach_campaign": parsed_outreach,
        "disclaimer": (
            "These outreach drafts were synthesized by local AI using verified evidence. "
            "Review and adapt messages before sending to prospects."
        ),
    }
