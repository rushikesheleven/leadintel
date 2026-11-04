# Changelog

All notable changes to the LeadIntel project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-11-04

### Added
- **MCP Server Core**: Official Python MCP SDK implementation (`leadintel-server`) with FastMCP / MCPServer architecture.
- **Business Discovery**:
  - `OpenStreetMapProvider` & `OverpassProvider` querying Nominatim and Overpass API with zero API keys or billing requirements.
  - Transparent fallback to `DemoProvider` when offline or when external services are unavailable.
  - Full ODbL 1.0 license compliance and attribution metadata.
- **Website Intelligence**:
  - `analyze_website`: Real-time HTTP/HTTPS, SSL certificate verification, meta tags, heading structures, mobile viewport checks, contact forms, and broken link spot-checking.
  - `check_seo`: Deterministic 100-point on-page technical SEO audit checking titles, descriptions, H1 uniqueness, image alt text, canonicals, robots.txt, and sitemap.xml.
  - `find_social_profiles`: Strict official profile extractor for LinkedIn, X/Twitter, Facebook, Instagram, YouTube, and Pinterest.
- **Competitor Intelligence**:
  - `find_competitors`: Geographic and semantic taxonomy matching to discover direct and indirect competitors in the same market.
  - `compare_businesses`: Side-by-side technical benchmarks comparing website performance, SEO scores, mobile readiness, and digital footprints.
- **Deterministic Lead Scoring**:
  - `score_lead`: 100-point evidence-based lead qualification engine assessing website quality, technical SEO, social channels, contact accessibility, mobile experience, and digital gaps.
  - Separate service opportunity scoring for Web Development, SEO, Social Media Management, and Combined Digital Growth packages.
  - Explicit evidence completeness percentage and confidence scoring.
- **Local AI Intelligence (Ollama)**:
  - `generate_business_insights`: Evidence-grounded business assessments, opportunity explanations, and package recommendations.
  - `generate_outreach`: Multi-channel outreach generator producing Cold Email pitches, LinkedIn connection messages, and WhatsApp Business outreach.
  - Strict local-first privacy: queries `http://localhost:11434` with zero cloud AI telemetry or data exfiltration.
- **Data Export & Reporting**:
  - `export_leads`: Supports multi-sheet publication-grade Excel (`.xlsx`) workbooks via OpenPyXL, CSV, and structured JSON.
  - `generate_business_report`: Synthesizes full 12-section business intelligence reports in Markdown, HTML (responsive CSS), and JSON formats.
- **Security Hardening**:
  - Server-Side Request Forgery (SSRF) defense with DNS resolution checks, carrier-grade NAT/private subnet blocking, and cloud metadata blocking (`169.254.169.254`, `fd00:ec2::254`, `100.100.100.200`, `metadata.google.internal`).
  - Redirect event hooks preventing SSRF bypasses across HTTP 3xx responses.
  - Dangerous service port filtering.
  - Path traversal validation (`validate_safe_export_path`) protecting system files and sensitive user credentials.
  - Spreadsheet formula injection sanitization for Excel and CSV outputs (`=, +, -, @, \t, \r` escaping).
  - Stored XSS defense via HTML entity escaping in business reports.
  - Dataclass credential redaction for configuration inspections.
