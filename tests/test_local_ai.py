"""
Unit and integration tests for Step 6: Local AI Integration using Ollama.

Covers:
- Successful generation with valid structured JSON
- Ollama server unavailable (ConnectError)
- Model unavailable (404 response)
- Invalid/malformed model response handling
- Request timeout handling
- Incomplete business data handling
- Outreach generation (Email, LinkedIn, WhatsApp)
- Evidence-based insights generation
- MCP tools execution for generate_business_insights and generate_outreach
- Registration of MCP tools
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from leadintel.server import mcp
from leadintel.services.ai_business_insights import (
    generate_ai_business_insights,
    generate_ai_outreach,
)
from leadintel.services.local_ai import (
    LocalAIClient,
    OllamaError,
    OllamaModelNotFoundError,
    OllamaUnavailableError,
)

# ── Sample Fixtures ───────────────────────────────────────────────────────────

SAMPLE_OLLAMA_INSIGHTS_RESPONSE = json.dumps({
    "executive_summary": "Acme Tech Solutions has an established digital foundation but exhibits technical SEO and mobile latency bottlenecks.",
    "opportunity_explanation": "Identified slow response times (> 2s) and missing H1 tags create a clear opening for performance optimization.",
    "lead_score_interpretation": "A score of 62/100 positions them as a Good Prospect with high leverage in web performance.",
    "competitor_insights": "Lags behind primary regional peers in mobile viewport responsiveness.",
    "service_recommendations": [
        {
            "service": "Website Development",
            "rationale": "Resolve mobile viewport configuration and server latency.",
            "priority": "High"
        },
        {
            "service": "SEO",
            "rationale": "Add missing canonical links and H1 heading tags.",
            "priority": "Medium"
        }
    ]
})

SAMPLE_OLLAMA_OUTREACH_RESPONSE = json.dumps({
    "email_pitch": {
        "subject": "Quick note regarding Acme Tech's mobile performance",
        "body": "Hi there, I noticed Acme Tech Solutions has strong local visibility in San Francisco, but your landing page is currently missing a mobile viewport configuration. Would you be open to a 10-minute chat on closing this gap?"
    },
    "linkedin_message": {
        "message": "Hi, love your work at Acme Tech Solutions. Noticed a couple of quick technical SEO quick-wins on your site. Would love to share insights."
    },
    "whatsapp_message": {
        "message": "Hello Acme Tech team! We analyzed digital performance in SF tech and found a 2-minute mobile optimization for your site. Let us know if you'd like the overview."
    }
})


# ── Local AI Client Tests ────────────────-------------------------------------

@pytest.mark.asyncio
class TestLocalAIClient:
    @respx.mock
    async def test_is_available_true(self):
        respx.get("http://localhost:11434/api/tags").mock(
            return_value=httpx.Response(200, json={"models": [{"name": "llama3:latest"}]})
        )
        client = LocalAIClient()
        assert await client.is_available() is True

    @respx.mock
    async def test_is_available_false_when_unreachable(self):
        respx.get("http://localhost:11434/api/tags").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        client = LocalAIClient()
        assert await client.is_available() is False

    @respx.mock
    async def test_list_models_success(self):
        respx.get("http://localhost:11434/api/tags").mock(
            return_value=httpx.Response(200, json={"models": [{"name": "llama3:latest"}, {"name": "mistral:latest"}]})
        )
        client = LocalAIClient()
        models = await client.list_models()
        assert "llama3:latest" in models
        assert "mistral:latest" in models

    @respx.mock
    async def test_check_model_installed(self):
        respx.get("http://localhost:11434/api/tags").mock(
            return_value=httpx.Response(200, json={"models": [{"name": "llama3:latest"}]})
        )
        client = LocalAIClient(model="llama3")
        assert await client.check_model_installed("llama3") is True
        assert await client.check_model_installed("gpt4") is False

    @respx.mock
    async def test_generate_success(self):
        respx.post("http://localhost:11434/api/generate").mock(
            return_value=httpx.Response(200, json={"response": "Hello from local Llama"})
        )
        client = LocalAIClient()
        out = await client.generate("Test prompt")
        assert out == "Hello from local Llama"

    @respx.mock
    async def test_generate_ollama_unavailable(self):
        respx.post("http://localhost:11434/api/generate").mock(
            side_effect=httpx.ConnectError("Ollama not running")
        )
        client = LocalAIClient()
        with pytest.raises(OllamaUnavailableError) as exc:
            await client.generate("Prompt")
        assert "not running" in str(exc.value)

    @respx.mock
    async def test_generate_model_not_found_404(self):
        respx.post("http://localhost:11434/api/generate").mock(
            return_value=httpx.Response(404, text="model not found")
        )
        client = LocalAIClient(model="nonexistent_model")
        with pytest.raises(OllamaModelNotFoundError) as exc:
            await client.generate("Prompt")
        assert "not found" in str(exc.value)

    @respx.mock
    async def test_generate_timeout_error(self):
        respx.post("http://localhost:11434/api/generate").mock(
            side_effect=httpx.ReadTimeout("Read timed out")
        )
        client = LocalAIClient(timeout=2.0)
        with pytest.raises(OllamaError) as exc:
            await client.generate("Prompt")
        assert "timed out" in str(exc.value)


# ── AI Business Insights Service Tests ────────────────────────────────────────

@pytest.mark.asyncio
class TestAIBusinessInsightsService:
    @respx.mock
    async def test_generate_business_insights_success(self):
        respx.post("http://localhost:11434/api/generate").mock(
            return_value=httpx.Response(200, json={"response": SAMPLE_OLLAMA_INSIGHTS_RESPONSE})
        )
        res = await generate_ai_business_insights(
            business_name="Acme Tech Solutions",
            business_category="Software Development",
            website_analysis={"available": True, "response_time_seconds": 2.2},
            seo_audit={"seo_score": 62.0},
        )
        assert res["business_name"] == "Acme Tech Solutions"
        assert res["is_ai_generated"] is True
        assert "executive_summary" in res["ai_insights"]
        assert len(res["ai_insights"]["service_recommendations"]) == 2

    @respx.mock
    async def test_generate_insights_handles_malformed_json_response(self):
        respx.post("http://localhost:11434/api/generate").mock(
            return_value=httpx.Response(200, json={"response": "Plain unstructured text from LLM."})
        )
        res = await generate_ai_business_insights(business_name="Rustic Woodworks")
        assert res["is_ai_generated"] is True
        assert "Plain unstructured text" in res["ai_insights"]["executive_summary"]

    async def test_generate_insights_rejects_empty_name(self):
        with pytest.raises(ValueError):
            await generate_ai_business_insights(business_name="")

    @respx.mock
    async def test_generate_insights_with_minimal_information(self):
        respx.post("http://localhost:11434/api/generate").mock(
            return_value=httpx.Response(200, json={"response": SAMPLE_OLLAMA_INSIGHTS_RESPONSE})
        )
        # Call with only business_name provided
        res = await generate_ai_business_insights(business_name="Solo Barber")
        assert res["business_name"] == "Solo Barber"
        assert res["verified_facts_grounding"]["category"] == "Unspecified"


# ── AI Outreach Generation Tests ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestAIOutreachGeneration:
    @respx.mock
    async def test_generate_outreach_success(self):
        respx.post("http://localhost:11434/api/generate").mock(
            return_value=httpx.Response(200, json={"response": SAMPLE_OLLAMA_OUTREACH_RESPONSE})
        )
        res = await generate_ai_outreach(
            business_name="Acme Tech Solutions",
            business_category="Software Development",
            agency_name="Apex Media",
            sender_name="Jane Doe",
        )
        assert res["business_name"] == "Acme Tech Solutions"
        assert res["is_ai_generated"] is True
        campaign = res["outreach_campaign"]
        assert "email_pitch" in campaign
        assert "linkedin_message" in campaign
        assert "whatsapp_message" in campaign
        assert "Acme Tech" in campaign["email_pitch"]["subject"]


# ── MCP Tools Step 6 Integration Tests ────────────────────────────────────────

@pytest.mark.asyncio
class TestMcpToolsStep6:
    @respx.mock
    async def test_mcp_generate_business_insights_success(self):
        respx.post("http://localhost:11434/api/generate").mock(
            return_value=httpx.Response(200, json={"response": SAMPLE_OLLAMA_INSIGHTS_RESPONSE})
        )
        res = await mcp.call_tool("generate_business_insights", {
            "business_name": "Acme Tech Solutions",
            "business_category": "Software Development",
        })
        content = res.content[0].text if hasattr(res.content[0], "text") else res.content[0]
        data = json.loads(content) if isinstance(content, str) else content

        assert data["business_name"] == "Acme Tech Solutions"
        assert data["is_ai_generated"] is True
        assert "executive_summary" in data["ai_insights"]

    @respx.mock
    async def test_mcp_generate_business_insights_ollama_unavailable(self):
        respx.post("http://localhost:11434/api/generate").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        res = await mcp.call_tool("generate_business_insights", {
            "business_name": "Acme Tech Solutions",
        })
        content = res.content[0].text if hasattr(res.content[0], "text") else res.content[0]
        data = json.loads(content) if isinstance(content, str) else content

        assert "error" in data
        assert "unavailable" in data["error"].lower()
        assert "ollama serve" in data["suggestion"].lower()

    @respx.mock
    async def test_mcp_generate_outreach_success(self):
        respx.post("http://localhost:11434/api/generate").mock(
            return_value=httpx.Response(200, json={"response": SAMPLE_OLLAMA_OUTREACH_RESPONSE})
        )
        res = await mcp.call_tool("generate_outreach", {
            "business_name": "BrightSpark Digital",
            "agency_name": "Growth Agency",
        })
        content = res.content[0].text if hasattr(res.content[0], "text") else res.content[0]
        data = json.loads(content) if isinstance(content, str) else content

        assert data["business_name"] == "BrightSpark Digital"
        assert "email_pitch" in data["outreach_campaign"]
        assert "linkedin_message" in data["outreach_campaign"]
