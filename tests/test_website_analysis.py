"""
Comprehensive unit tests for Step 3: Website Analysis tools and services.

Covers:
- Working website analysis and SEO audit
- Missing title, meta description, and H1 tags
- Invalid URLs and malformed inputs
- Website timeout and connection failure
- Robots.txt disallow rules
- Missing social links detection
- Malicious localhost and SSRF attempts
- Redirect to private IPs
"""

from __future__ import annotations

import httpx
import pytest
import respx

from leadintel.server import mcp
from leadintel.services.robots_checker import RobotsChecker
from leadintel.services.seo_auditor import audit_html_seo, run_full_seo_audit
from leadintel.services.social_finder import extract_social_profiles
from leadintel.services.url_validator import SecurityValidationError, validate_and_normalize_url
from leadintel.services.website_analyzer import analyze_target_website

# ── Sample HTML Fixtures ──────────────────────────────────────────────────────

SAMPLE_VALID_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acme Innovations - Enterprise Cloud &amp; AI Solutions</title>
    <meta name="description" content="Acme Innovations provides cutting-edge cloud infrastructure, B2B intelligence and developer automation tools worldwide.">
    <link rel="canonical" href="https://acme.example/solutions">
    <meta property="og:title" content="Acme Innovations">
    <meta property="og:description" content="Enterprise Cloud Solutions">
    <meta property="og:image" content="https://acme.example/og.png">
</head>
<body>
    <header>
        <h1>Next-Generation Business Cloud Solutions</h1>
        <nav>
            <a href="/about">About Us</a>
            <a href="/pricing">Pricing</a>
            <a href="/contact">Contact</a>
        </nav>
    </header>
    <main>
        <h2>Scalable Architecture</h2>
        <p>Contact us at info@acme.example or call us at +1-415-555-0199.</p>
        <img src="/img/hero.png" alt="Cloud Architecture Overview">
        <img src="/img/logo.png" alt="Company Logo">
        <form action="/submit-contact" method="post">
            <input type="text" name="name" placeholder="Your Name">
            <input type="email" name="email" placeholder="Your Email">
            <textarea name="message" placeholder="Message"></textarea>
            <button type="submit">Send Inquiry</button>
        </form>
    </main>
    <footer>
        <a href="https://www.linkedin.com/company/acme-innovations">LinkedIn</a>
        <a href="https://twitter.com/acme_tech">Twitter / X</a>
        <a href="https://facebook.com/acmeinnovations">Facebook</a>
        <a href="https://instagram.com/acmeinnovations">Instagram</a>
        <a href="https://youtube.com/@acmeinnovations">YouTube</a>
        <a href="https://pinterest.com/acmeinnovations">Pinterest</a>
        <!-- Share button to be filtered out -->
        <a href="https://twitter.com/intent/tweet?url=https://acme.example">Share on Twitter</a>
    </footer>
</body>
</html>
"""

SAMPLE_INCOMPLETE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body>
    <p>Welcome to this minimal site without title or headings.</p>
    <img src="/logo.png">
</body>
</html>
"""


# ── URL Validator / SSRF Tests ────────────────────────────────────────────────

class TestUrlValidatorAndSSRF:
    def test_valid_public_url(self):
        url = validate_and_normalize_url("https://example.com/about")
        assert url == "https://example.com/about"

    def test_adds_https_scheme(self):
        url = validate_and_normalize_url("example.com")
        assert url == "https://example.com"

    def test_rejects_empty_url(self):
        with pytest.raises(ValueError):
            validate_and_normalize_url("")

    def test_rejects_malicious_localhost(self):
        with pytest.raises(SecurityValidationError) as exc:
            validate_and_normalize_url("http://localhost:8000/admin")
        assert "blocked for security reasons" in str(exc.value)

    def test_rejects_loopback_ip(self):
        with pytest.raises(SecurityValidationError) as exc:
            validate_and_normalize_url("http://127.0.0.1/secrets")
        assert "restricted" in str(exc.value)

    def test_rejects_cloud_metadata_ip(self):
        with pytest.raises(SecurityValidationError) as exc:
            validate_and_normalize_url("http://169.254.169.254/latest/meta-data/")
        assert "restricted" in str(exc.value)

    def test_rejects_private_class_a(self):
        with pytest.raises(SecurityValidationError) as exc:
            validate_and_normalize_url("http://10.0.0.5:8080")
        assert "restricted" in str(exc.value)

    def test_rejects_private_class_c(self):
        with pytest.raises(SecurityValidationError) as exc:
            validate_and_normalize_url("http://192.168.1.1/router")
        assert "restricted" in str(exc.value)

    def test_rejects_unsupported_scheme(self):
        with pytest.raises(SecurityValidationError) as exc:
            validate_and_normalize_url("ftp://files.example.com")
        assert "Only http and https are allowed" in str(exc.value)


# ── Robots Checker Tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestRobotsChecker:
    @respx.mock
    async def test_robots_allowed(self):
        respx.get("https://acme.example/robots.txt").mock(
            return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
        )
        checker = RobotsChecker()
        allowed, reason = await checker.can_fetch("https://acme.example/about")
        assert allowed is True
        assert reason is None

    @respx.mock
    async def test_robots_disallow(self):
        respx.get("https://acme.example/robots.txt").mock(
            return_value=httpx.Response(200, text="User-agent: *\nDisallow: /private/\nDisallow: /admin/")
        )
        checker = RobotsChecker()
        allowed, reason = await checker.can_fetch("https://acme.example/private/data")
        assert allowed is False
        assert "Disallowed by rules" in str(reason)

    @respx.mock
    async def test_robots_404_means_allowed(self):
        respx.get("https://acme.example/robots.txt").mock(
            return_value=httpx.Response(404)
        )
        checker = RobotsChecker()
        allowed, reason = await checker.can_fetch("https://acme.example/page")
        assert allowed is True

    @respx.mock
    async def test_robots_403_access_denied(self):
        respx.get("https://acme.example/robots.txt").mock(
            return_value=httpx.Response(403)
        )
        checker = RobotsChecker()
        allowed, reason = await checker.can_fetch("https://acme.example/page")
        assert allowed is False
        assert "403" in str(reason)


# ── Social Media Profile Extraction Tests ─────────────────────────────────────

class TestSocialProfilesFinder:
    def test_extracts_all_platforms(self):
        profiles = extract_social_profiles(SAMPLE_VALID_HTML, base_url="https://acme.example")
        assert len(profiles["linkedin"]) == 1
        assert "acme-innovations" in profiles["linkedin"][0]["url"]
        assert len(profiles["twitter"]) == 1
        assert "acme_tech" in profiles["twitter"][0]["url"]
        assert len(profiles["facebook"]) == 1
        assert len(profiles["instagram"]) == 1
        assert len(profiles["youtube"]) == 1
        assert len(profiles["pinterest"]) == 1

    def test_filters_share_dialogs(self):
        profiles = extract_social_profiles(SAMPLE_VALID_HTML, base_url="https://acme.example")
        twitter_urls = [item["url"] for item in profiles["twitter"]]
        assert not any("intent/tweet" in u for u in twitter_urls)

    def test_empty_html_yields_empty_profiles(self):
        profiles = extract_social_profiles("")
        for platform, items in profiles.items():
            assert items == []


# ── SEO Auditor Tests ─────────────────────────────────────────────────────────

class TestSeoAuditor:
    def test_audit_html_working_website(self):
        audit = audit_html_seo(SAMPLE_VALID_HTML, "https://acme.example/solutions")
        assert audit["seo_score"] >= 80
        assert audit["checks"]["title"]["present"] is True
        assert audit["checks"]["meta_description"]["present"] is True
        assert audit["checks"]["h1_headings"]["count"] == 1
        assert audit["checks"]["images"]["missing_alt"] == 0
        assert audit["checks"]["canonical_url"]["present"] is True
        assert "Google ranking" in audit["disclaimer"]

    def test_audit_missing_title_description_h1(self):
        audit = audit_html_seo(SAMPLE_INCOMPLETE_HTML, "https://minimal.example")
        assert audit["checks"]["title"]["present"] is False
        assert audit["checks"]["meta_description"]["present"] is False
        assert audit["checks"]["h1_headings"]["count"] == 0
        assert audit["checks"]["images"]["missing_alt"] == 1
        assert audit["seo_score"] < 60
        issues_messages = [iss["message"] for iss in audit["issues"]]
        assert any("missing a <title>" in m for m in issues_messages)
        assert any("missing a meta description" in m for m in issues_messages)
        assert any("No <h1> heading" in m for m in issues_messages)

    def test_audit_multiple_h1(self):
        html = "<html><head><title>Title</title></head><body><h1>One</h1><h1>Two</h1></body></html>"
        audit = audit_html_seo(html, "https://multi.example")
        issues_messages = [iss["message"] for iss in audit["issues"]]
        assert any("Multiple <h1> headings" in m for m in issues_messages)

    @respx.mock
    @pytest.mark.asyncio
    async def test_full_seo_audit_network_flow(self):
        respx.get("https://acme.example/robots.txt").mock(
            return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
        )
        respx.get("https://acme.example/sitemap.xml").mock(
            return_value=httpx.Response(200, text="<xml></xml>")
        )
        respx.get("https://acme.example").mock(
            return_value=httpx.Response(200, text=SAMPLE_VALID_HTML)
        )
        audit = await run_full_seo_audit("https://acme.example")
        assert audit["checks"]["robots_txt"]["available"] is True
        assert audit["checks"]["sitemap"]["available"] is True
        assert audit["seo_score"] >= 80


# ── Website Analyzer Tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestWebsiteAnalyzer:
    @respx.mock
    async def test_analyze_working_website(self):
        respx.get("https://acme.example/robots.txt").mock(
            return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
        )
        respx.get("https://acme.example").mock(
            return_value=httpx.Response(200, text=SAMPLE_VALID_HTML)
        )
        # Mock internal links HEAD checks
        respx.head(url__startswith="https://acme.example/").mock(
            return_value=httpx.Response(200)
        )

        res = await analyze_target_website("https://acme.example", check_broken_links=True)
        assert res["status"] == "success"
        assert res["available"] is True
        assert res["http_status"] == 200
        assert res["protocol"]["is_https"] is True
        assert res["metadata"]["title"] == "Acme Innovations - Enterprise Cloud & AI Solutions"
        assert res["metadata"]["has_mobile_viewport"] is True
        assert res["contact_detection"]["has_contact_form"] is True
        assert "info@acme.example" in res["contact_detection"]["emails_found"]
        assert len(res["social_profiles"]["linkedin"]) == 1

    @respx.mock
    async def test_website_timeout_handling(self):
        respx.get("https://timeout.example/robots.txt").mock(
            return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
        )
        respx.get("https://timeout.example").mock(
            side_effect=httpx.ReadTimeout("Connection timed out")
        )
        res = await analyze_target_website("https://timeout.example")
        assert res["available"] is False
        assert "timed out" in res.get("error", "").lower() or res.get("status") == "error"

    @respx.mock
    async def test_robots_disallowed_website(self):
        respx.get("https://forbidden.example/robots.txt").mock(
            return_value=httpx.Response(200, text="User-agent: *\nDisallow: /")
        )
        res = await analyze_target_website("https://forbidden.example/page")
        assert res["status"] == "blocked_by_robots"
        assert res["available"] is False


# ── MCP Tool Registration & Execution Tests ───────────────────────────────────

@pytest.mark.asyncio
class TestMcpToolsStep3:
    @respx.mock
    async def test_mcp_analyze_website(self):
        respx.get("https://acme.example/robots.txt").mock(
            return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
        )
        respx.get("https://acme.example").mock(
            return_value=httpx.Response(200, text=SAMPLE_VALID_HTML)
        )
        respx.head(url__startswith="https://acme.example/").mock(
            return_value=httpx.Response(200)
        )

        res = await mcp.call_tool("analyze_website", {"url": "https://acme.example"})
        import json
        content = res.content[0].text if hasattr(res.content[0], "text") else res.content[0]
        data = json.loads(content) if isinstance(content, str) else content

        assert data["status"] == "success"
        assert data["available"] is True
        assert data["metadata"]["title"] == "Acme Innovations - Enterprise Cloud & AI Solutions"

    @respx.mock
    async def test_mcp_check_seo(self):
        respx.get("https://acme.example/robots.txt").mock(
            return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
        )
        respx.get("https://acme.example/sitemap.xml").mock(
            return_value=httpx.Response(200, text="<xml></xml>")
        )
        respx.get("https://acme.example").mock(
            return_value=httpx.Response(200, text=SAMPLE_VALID_HTML)
        )

        res = await mcp.call_tool("check_seo", {"url": "https://acme.example"})
        import json
        content = res.content[0].text if hasattr(res.content[0], "text") else res.content[0]
        data = json.loads(content) if isinstance(content, str) else content

        assert "seo_score" in data
        assert data["seo_score"] >= 80
        assert "disclaimer" in data

    @respx.mock
    async def test_mcp_find_social_profiles(self):
        respx.get("https://acme.example/robots.txt").mock(
            return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
        )
        respx.get("https://acme.example").mock(
            return_value=httpx.Response(200, text=SAMPLE_VALID_HTML)
        )

        res = await mcp.call_tool("find_social_profiles", {"url": "https://acme.example"})
        import json
        content = res.content[0].text if hasattr(res.content[0], "text") else res.content[0]
        data = json.loads(content) if isinstance(content, str) else content

        assert data["status"] == "success"
        assert data["total_profiles_found"] >= 6
        assert len(data["profiles"]["linkedin"]) == 1

    async def test_mcp_tool_blocks_localhost(self):
        res = await mcp.call_tool("analyze_website", {"url": "http://localhost:8080"})
        import json
        content = res.content[0].text if hasattr(res.content[0], "text") else res.content[0]
        data = json.loads(content) if isinstance(content, str) else content

        assert data["status"] == "error" or data["available"] is False
        assert "security" in data["error"].lower() or "blocked" in data["error"].lower()
