# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

---

## Reporting a Vulnerability

The LeadIntel team takes security vulnerabilities seriously. We ask that vulnerabilities be reported responsibly and privately before public disclosure.

- **Email**: Send vulnerability reports directly to `rushikesheleven@gmail.com` with the subject tag `[SECURITY: LeadIntel]`.
- **Response Target**: We will acknowledge receipt within 48 hours and provide an estimated timeline for remediation.
- **Coordination**: Please do not file public GitHub issues for undisclosed security vulnerabilities.

---

## Security Architecture & Built-in Safeguards

LeadIntel is designed with a defense-in-depth security architecture suitable for AI agents and developer workstations:

### 1. Server-Side Request Forgery (SSRF) Protection
- **Scheme Restriction**: Strictly allows `http://` and `https://`. All other URI schemes (e.g., `file://`, `ftp://`, `gopher://`, `data://`) are rejected.
- **Private & Restricted IP Blocking**: Validates all target IPs against non-global, loopback, link-local, multicast, and RFC 1918 private subnets (`127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `::1`, `fc00::/7`).
- **Cloud Metadata Protection**: Explicitly blocks cloud instance metadata endpoints across major providers:
  - AWS/GCP/Azure/DigitalOcean: `169.254.169.254`
  - AWS IMDSv2 IPv6: `fd00:ec2::254`
  - Google Cloud: `metadata.google.internal`, `metadata.google`, `metadata`
  - Alibaba Cloud: `100.100.100.200`
- **Internal Domain Blocking**: Restricts queries resolving to internal TLDs (`.local`, `.localhost`, `.internal`, `.lan`, `.corp`, `.home`).
- **Port Allowlist / Dangerous Port Blocking**: Prohibits probes against non-web infrastructure ports (e.g., 22/SSH, 25/SMTP, 3306/MySQL, 5432/PostgreSQL, 6379/Redis, 11211/Memcached, 27017/MongoDB).

### 2. DNS Rebinding & Redirect Validation
- **Redirect Event Hooks**: Every HTTP 3xx redirect is intercepted via an event hook and re-validated through SSRF filters before the client follows the redirect.
- **Hop Limit**: Enforces a strict maximum of 5 redirects to prevent infinite redirect loops or crawler tarpits.

### 3. Path Traversal & File Protection
- **Export Destination Sanitization**: Validates all export file paths (`validate_safe_export_path`) against directory traversal sequences (`..`), null bytes (`\0`), and protected system paths (`/etc`, `/bin`, `/usr`, `/root`, `/dev`, `/sys`, `/proc`, `C:\Windows`).
- **User Directory Isolation**: Restricts writes from targeting sensitive user configuration directories (e.g., `~/.ssh`, `~/.gnupg`, `~/.aws`, shell startup files).
- **Extension Enforcement**: Requires exported files to end with explicitly allowed extensions (`.xlsx`, `.csv`, `.json`).

### 4. Spreadsheet Formula Injection (CSV / Excel Injection)
- **Cell Sanitization**: All exported tabular lead attributes and cell contents starting with formula trigger prefixes (`=`, `+`, `-`, `@`, `\t`, `\r`) are automatically escaped with a leading single quote (`'`), rendering them as safe text literals in Microsoft Excel, Google Sheets, and LibreOffice Calc.

### 5. Stored XSS Mitigation in HTML Reports
- **HTML Sanitization**: All dynamically populated fields (business names, categories, websites, competitor names, outreach copy) rendered into HTML executive reports are sanitized using standard HTML entity escaping (`html.escape`).

### 6. Local-First Privacy & Zero Cloud Exfiltration
- **No Remote Telemetry**: LeadIntel does not transmit analytics, logs, or usage metrics to external servers.
- **No Cloud AI Dependencies**: Lead scoring is deterministic and performed locally. Optional AI summarization uses local Ollama instances (`http://localhost:11434`) without remote data egress.
- **Secret Redaction**: Config objects mask third-party credentials (`***`) during serialization, logging, and representation inspection.

---

## Ethical Crawling & Licensing Compliance

- **Robots.txt Adherence**: Checks website `robots.txt` before crawling; honors `Disallow` directives.
- **OpenStreetMap Attribution**: Respects OpenStreetMap terms of use and attributes data under the Open Database License (ODbL 1.0).
- **Rate Throttling & Payload Caps**: Limits crawled payload size (5 MB max) and caps spot-check internal links (10 max) with respectful request timeouts (15s).
