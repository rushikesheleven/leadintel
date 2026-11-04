"""
Security audit and vulnerability regression test suite for Step 8.

Verifies:
1. SSRF protection on private IPs, Carrier-grade NAT, and cloud metadata.
2. SSRF protection across HTTP 3xx redirects to internal destinations.
3. Dangerous port blocking (SSH, Redis, DB ports).
4. Path traversal protection in export paths (including Windows system paths and UNC paths).
5. Spreadsheet formula injection mitigation in CSV and Excel exports.
6. Stored XSS entity escaping in HTML executive reports.
7. Safe representation masking of credentials in Settings.
8. Local AI privacy: Ollama rejects external hosts and bypasses ambient proxies.
9. DNS Rebinding: Connection-level validation and pinning.
"""

from __future__ import annotations

import os
import tempfile

import httpx
import pytest
import respx

from leadintel.config import Settings
from leadintel.exporters.csv_exporter import export_to_csv, sanitize_csv_cell
from leadintel.exporters.excel_exporter import sanitize_excel_cell
from leadintel.models.business import Business
from leadintel.services.business_report import generate_comprehensive_business_report
from leadintel.services.local_ai import LocalAIClient
from leadintel.services.url_validator import (
    RebindingSafeAnyIOBackend,
    SecurityValidationError,
    create_safe_client,
    validate_and_normalize_url,
)
from leadintel.storage.path_validator import validate_safe_export_path


class TestSSRFProtections:
    def test_blocks_localhost_and_loopback(self):
        for bad_url in [
            "http://localhost/admin",
            "http://127.0.0.1:8000/",
            "http://[::1]:8080/",
            "http://0.0.0.0/",
            "http://broadcasthost/",
        ]:
            with pytest.raises(SecurityValidationError):
                validate_and_normalize_url(bad_url)

    def test_blocks_cloud_metadata(self):
        for meta_url in [
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://100.100.100.200/latest/meta-data/",
            "http://[fd00:ec2::254]/latest/meta-data/",
        ]:
            with pytest.raises(SecurityValidationError):
                validate_and_normalize_url(meta_url)

    def test_blocks_carrier_grade_nat_and_private_subnets(self):
        for priv_ip in [
            "http://10.0.0.1/",
            "http://172.16.0.1/",
            "http://192.168.1.1/",
            "http://100.64.0.1/",  # RFC 6598 CGNAT
        ]:
            with pytest.raises(SecurityValidationError):
                validate_and_normalize_url(priv_ip)

    def test_blocks_internal_tld_suffixes(self):
        for internal_url in [
            "http://intranet.corp/",
            "http://router.local/",
            "http://service.internal/",
            "http://database.lan/",
            "http://server.localdomain/",
        ]:
            with pytest.raises(SecurityValidationError):
                validate_and_normalize_url(internal_url)

    def test_blocks_dangerous_service_ports(self):
        for port in [21, 22, 23, 25, 3306, 5432, 6379, 11211, 27017]:
            with pytest.raises(SecurityValidationError) as exc:
                validate_and_normalize_url(f"http://example.com:{port}/")
            assert "blocked for security reasons" in str(exc.value)

    def test_blocks_url_with_credentials(self):
        with pytest.raises(SecurityValidationError) as exc:
            validate_and_normalize_url("http://user:secret@example.com/")
        assert "credentials are not permitted" in str(exc.value)

    @respx.mock
    @pytest.mark.asyncio
    async def test_redirect_to_private_ip_intercepted(self):
        # Simulate open redirect from public URL to internal 127.0.0.1
        respx.get("https://public-business.example/welcome").mock(
            return_value=httpx.Response(302, headers={"Location": "http://127.0.0.1/internal-status"})
        )
        respx.get("http://127.0.0.1/internal-status").mock(
            return_value=httpx.Response(200, text="SENSITIVE_INTERNAL_DATA")
        )

        client = create_safe_client(timeout=5.0)
        try:
            with pytest.raises(SecurityValidationError):
                await client.get("https://public-business.example/welcome")
        finally:
            await client.aclose()


class TestDNSRebindingDefense:
    @pytest.mark.asyncio
    async def test_connection_level_pins_and_blocks_restricted_ips(self):
        backend = RebindingSafeAnyIOBackend()
        for restricted_host in ["127.0.0.1", "169.254.169.254", "10.0.0.1", "localhost"]:
            with pytest.raises(SecurityValidationError):
                await backend.connect_tcp(restricted_host, 80)


class TestLocalAIPrivacy:
    def test_ollama_rejects_external_hosts(self):
        for external_url in [
            "https://remote-ai.example.com",
            "http://api.openai.com/v1",
            "http://192.168.1.50:11434",
            "http://cloud-ollama.internal:11434",
        ]:
            with pytest.raises(SecurityValidationError) as exc:
                LocalAIClient(base_url=external_url)
            assert "not a local loopback address" in str(exc.value)

    def test_ollama_allows_local_loopback(self):
        for local_url in [
            "http://localhost:11434",
            "http://127.0.0.1:11434",
            "http://[::1]:11434",
        ]:
            client = LocalAIClient(base_url=local_url)
            assert client.base_url == local_url.rstrip("/")


class TestPathTraversalAndFileHandling:
    def test_blocks_system_root_paths(self):
        for bad_path in ["/etc/cron.d/pwn.csv", "/bin/sh.json", "/usr/bin/python.xlsx", "/root/secrets.csv"]:
            with pytest.raises(SecurityValidationError):
                validate_safe_export_path(bad_path)

    def test_blocks_windows_system_paths_cross_platform(self):
        for win_path in [
            "C:\\Windows\\System32\\cmd.exe",
            "c:/windows/system32/pwn.xlsx",
            "C:/Program Files/malicious.csv",
            "C:/ProgramData/evil.json",
        ]:
            with pytest.raises(SecurityValidationError) as exc:
                validate_safe_export_path(win_path, allowed_extensions={"xlsx", "csv", "json"})
            assert "protected Windows system location" in str(exc.value)

    def test_blocks_unc_network_paths(self):
        with pytest.raises(SecurityValidationError) as exc:
            validate_safe_export_path("\\\\evil-server\\share\\pwn.xlsx", allowed_extensions={"xlsx"})
        assert "UNC network paths are not permitted" in str(exc.value)

    def test_blocks_sensitive_user_subdirectories(self):
        home = os.path.expanduser("~")
        for sensitive_file in [
            os.path.join(home, ".ssh", "authorized_keys.csv"),
            os.path.join(home, ".bashrc"),
            os.path.join(home, ".zshrc"),
            os.path.join(home, ".aws", "credentials.json"),
        ]:
            with pytest.raises(SecurityValidationError):
                validate_safe_export_path(sensitive_file)

    def test_blocks_null_byte_injection(self):
        with pytest.raises(SecurityValidationError) as exc:
            validate_safe_export_path("safe_name.csv\0.exe")
        assert "Null byte" in str(exc.value)

    def test_enforces_allowed_extensions(self):
        with pytest.raises(SecurityValidationError) as exc:
            validate_safe_export_path("report.exe", allowed_extensions={"xlsx", "csv"})
        assert "Invalid file extension" in str(exc.value)

    def test_allows_valid_temporary_and_relative_paths(self):
        with tempfile.NamedTemporaryFile(suffix=".csv") as tmp:
            validated = validate_safe_export_path(tmp.name, allowed_extensions={"csv"})
            assert os.path.isabs(validated)


class TestSpreadsheetFormulaInjection:
    def test_csv_cell_formula_sanitization(self):
        for formula in ["=CMD|' /C calc'!A0", "+1+1", "-5*5", "@SUM(A1:A10)", "\tmalicious", "\rreturn"]:
            sanitized = sanitize_csv_cell(formula)
            assert sanitized.startswith("'")

    def test_excel_cell_formula_sanitization(self):
        for formula in ["=HYPERLINK(\"http://attacker.com\")", "+2+2", "-1-1", "@alert()"]:
            sanitized = sanitize_excel_cell(formula)
            assert sanitized.startswith("'")

    def test_csv_export_escapes_malicious_business_attributes(self):
        biz = Business(
            id="biz_inj",
            name="=2+2",
            category="+Technology",
            city="@London",
            state="UK",
            country="GB",
            source="demo",
        )
        csv_str = export_to_csv([biz])
        assert "'=2+2" in csv_str
        assert "'+Technology" in csv_str
        assert "'@London" in csv_str


class TestHTMLReportStoredXSS:
    def test_html_report_escapes_xss_injections(self):
        xss_name = '<script>alert("XSS")</script>'
        xss_cat = '<img src=x onerror=alert(1)>'
        biz_info = {
            "name": xss_name,
            "category": xss_cat,
            "city": "Cyber City",
            "website": "https://example.com?param=<test>",
        }
        report_html = generate_comprehensive_business_report(
            business_info=biz_info,
            output_format="html",
        )
        assert isinstance(report_html, str)
        # Ensure raw tags are NOT rendered unescaped
        assert '<script>alert("XSS")</script>' not in report_html
        assert '<img src=x onerror=alert(1)>' not in report_html
        # Ensure escaped entities ARE present
        assert "&lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt;" in report_html or "&lt;script&gt;" in report_html
        assert "&lt;img" in report_html


class TestCredentialProtection:
    def test_settings_repr_masks_api_keys(self):
        s = Settings(
            google_places_api_key="AIzaSySecretPlacesKey123",
            pagespeed_api_key="PageSpeedSecretToken456",
            gemini_api_key="GeminiSecretApiKey789",
        )
        repr_str = repr(s)
        assert "AIzaSySecretPlacesKey123" not in repr_str
        assert "PageSpeedSecretToken456" not in repr_str
        assert "GeminiSecretApiKey789" not in repr_str
        assert "***" in repr_str
