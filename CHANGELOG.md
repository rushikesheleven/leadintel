# Changelog

All notable changes to the LeadIntel project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.1] - 2026-11-04

### Fixed
- **OSM Policy Compliance — Overpass headers**: Removed the `Referer: https://overpass-turbo.eu/`
  header from Overpass API requests. LeadIntel was falsely presenting itself as the Overpass Turbo
  web application. The header is now omitted entirely; `User-Agent` correctly identifies the client
  as `LeadIntel/0.1.1`.
- **OSM Policy Compliance — Nominatim User-Agent**: Updated `User-Agent` to
  `LeadIntel/0.1.1 (open-source B2B lead-generation MCP server; https://github.com/example/leadintel)`
  per the [Nominatim Acceptable Use Policy](https://operations.osmfoundation.org/policies/nominatim/).
- **Nominatim global rate-limit**: Introduced a module-level `asyncio.Lock`-protected rate-limiter
  (`_nominatim_rate_limit()`) that enforces a minimum 1-second gap between *all* Nominatim HTTP
  requests across every `OverpassProvider` instance in the same process. Previously each instance
  had its own independent clock, allowing concurrent tool calls to exceed the 1 req/s policy limit.
- **Nominatim geocode cache**: Added a 24-hour in-process geocode cache (`_nominatim_geocode_cache`)
  keyed by location string. Repeated searches for the same city (e.g. multiple category searches for
  "Pune") reuse the cached bounding box without issuing redundant geocode requests.
- **Silent fallback eliminated**: Live searches with a location parameter no longer silently fall
  through to `DemoProvider`; errors and zero-result live searches are reported with an explicit
  `source="openstreetmap"` and a human-readable `note`.
- **Overpass query robustness**:
  - POI queries restricted to `node` and `way` elements (heavy administrative `relation` objects
    excluded) to prevent server-side timeouts.
  - Search bounding box centred on the geocoded coordinate with the configured `radius_m` (5 km
    default) instead of the multi-hundred-kilometre administrative boundary returned by Nominatim.
  - Mirror endpoints (`lz4`, `z`, `private.coffee`) tried automatically when the primary server
    returns 502 or times out.
- **Nominatim POI fallback**: When all Overpass mirrors are at capacity or timeout, the provider
  seamlessly falls back to a live Nominatim POI search under the same ODbL licence.
- **Environment file discovery** (`config.py`): `.env` is now located via
  `LEADINTEL_ENV_FILE` → `cwd` → repo root → ancestor walk, so Claude Desktop subprocess launches
  from `/` or `~` correctly pick up project configuration.

### Changed
- `BusinessSearchResult` model gains an optional `error` field surfacing provider error details.
- `search_businesses` MCP tool response includes a human-readable `note` for live results, zero
  results, and error conditions so callers can distinguish live OSM data from empty results.

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
