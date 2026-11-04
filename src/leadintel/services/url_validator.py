"""
URL and Host Validation Service for SSRF protection and security checks.

Prevents SSRF and DNS Rebinding attacks by:
- Enforcing http/https schemes only.
- Rejecting userinfo/credentials in URLs.
- Rejecting dangerous service ports (e.g., SSH, SMTP, Redis, DB ports).
- Blocking localhost, 127.0.0.1, ::1, 0.0.0.0, broadcasthost, and internal hostnames.
- Blocking non-global IP addresses, link-local, loopbacks, and private subnets (RFC 1918, RFC 6598 CGNAT).
- Blocking cloud metadata endpoints (169.254.169.254, metadata.google.internal, fd00:ec2::254, 100.100.100.200).
- Blocking internal and local domain suffixes (.local, .localhost, .internal, .lan, .corp, .home).
- Mitigating DNS Rebinding & TOCTOU: Validating all mixed DNS answers and pinning the TCP socket connection directly to the verified public IP.
- Bypassing ambient proxies (trust_env=False) to prevent proxy-based SSRF bypass.
- Validating HTTP redirects to prevent open redirect SSRF bypasses.
- Providing safe pre-configured HTTPX clients and transports.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpcore
import httpx
from httpcore._backends.anyio import AnyIOBackend, AnyIOStream

logger = logging.getLogger(__name__)

# Cloud metadata IPs, loopbacks, and internal hostnames explicitly blocked
BLOCKED_IP_STRINGS = {
    "169.254.169.254",          # AWS/GCP/Azure/DigitalOcean metadata (IPv4)
    "fd00:ec2::254",            # AWS IMDSv2 (IPv6)
    "100.100.100.200",          # Alibaba Cloud metadata
    "metadata.google.internal", # GCP metadata DNS
    "metadata.google",          # GCP metadata alias
    "metadata",                 # Cloud generic metadata hostname
    "instance-data",            # EC2 instance data hostname
}

BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "broadcasthost",
}

BLOCKED_HOST_SUFFIXES = (
    ".local",
    ".localhost",
    ".internal",
    ".lan",
    ".localdomain",
    ".corp",
    ".home",
)

# Ports associated with sensitive backend services that should never be probed by a website crawler
DANGEROUS_PORTS = {
    21,    # FTP
    22,    # SSH
    23,    # Telnet
    25,    # SMTP
    53,    # DNS
    110,   # POP3
    111,   # RPC
    135,   # RPC
    139,   # NetBIOS
    143,   # IMAP
    445,   # SMB
    1433,  # MSSQL
    1521,  # Oracle
    2049,  # NFS
    3306,  # MySQL
    3389,  # RDP
    5432,  # PostgreSQL
    5900,  # VNC
    6379,  # Redis
    11211, # Memcached
    27017, # MongoDB
    28017, # MongoDB Web
}


class SecurityValidationError(ValueError):
    """Raised when a URL violates safety or SSRF restrictions."""


def is_ip_private_or_restricted(ip_str: str) -> bool:
    """
    Check if an IP string belongs to private, loopback, link-local, multicast,
    non-global, or reserved ranges.
    """
    try:
        ip = ipaddress.ip_address(ip_str.strip("[]"))
        # Check IPv4-mapped IPv6 address (e.g. ::ffff:127.0.0.1)
        mapped = getattr(ip, "ipv4_mapped", None)
        if mapped and (not mapped.is_global or mapped.is_private or mapped.is_loopback):
            return True

        return (
            not ip.is_global
            or ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return True


def validate_and_normalize_url(url: str) -> str:
    """
    Validate a URL string for safety against SSRF and syntax issues.

    Returns the normalized URL string if valid.
    Raises SecurityValidationError or ValueError if invalid or unsafe.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string.")

    url = url.strip()
    parsed_initial = urlparse(url)
    if parsed_initial.scheme and parsed_initial.scheme not in ("http", "https"):
        raise SecurityValidationError(f"Invalid scheme '{parsed_initial.scheme}'. Only http and https are allowed.")

    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise SecurityValidationError(f"Invalid scheme '{parsed.scheme}'. Only http and https are allowed.")

    # Disallow credentials in URLs to prevent credential confusion/leakage
    if parsed.username or parsed.password:
        raise SecurityValidationError("URLs containing embedded username or password credentials are not permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise SecurityValidationError("URL missing valid hostname.")

    hostname_lower = hostname.lower().strip("[]")

    if hostname_lower in BLOCKED_HOSTNAMES or hostname_lower in BLOCKED_IP_STRINGS:
        raise SecurityValidationError(f"Access to restricted host '{hostname}' is blocked for security reasons (SSRF protection).")

    if hostname_lower.endswith(BLOCKED_HOST_SUFFIXES):
        raise SecurityValidationError(f"Access to internal domain '{hostname}' is blocked for security reasons (SSRF protection).")

    # Check dangerous port restrictions
    if parsed.port and parsed.port in DANGEROUS_PORTS:
        raise SecurityValidationError(f"Access to dangerous port {parsed.port} is blocked for security reasons.")

    # Check if hostname directly represents an IP literal
    try:
        if is_ip_private_or_restricted(hostname_lower):
            raise SecurityValidationError(f"Access to IP '{hostname}' is restricted (private/loopback/cloud metadata).")
    except ValueError:
        pass

    # Resolve hostname via DNS to verify target IP isn't private / non-global.
    # Checks ALL returned addresses (handles mixed IPv4/IPv6 answers).
    try:
        addrinfo = socket.getaddrinfo(hostname, None)
        for family, socktype, proto, canonname, sockaddr in addrinfo:
            ip_str = sockaddr[0]
            if is_ip_private_or_restricted(ip_str) or ip_str in BLOCKED_IP_STRINGS:
                raise SecurityValidationError(
                    f"Host '{hostname}' resolved to restricted IP '{ip_str}' (SSRF protection)."
                )
    except socket.gaierror as e:
        logger.debug("DNS resolution failed for '%s': %s", hostname, e)
        # We allow DNS resolution failures to proceed to HTTP request where HTTPX will cleanly handle connection error,
        # unless it was specifically blocked above.

    return url


async def validate_redirect_hook(response: httpx.Response) -> None:
    """
    HTTPX event hook that intercepts 3xx redirects and validates the destination URL against SSRF rules.
    Prevents malicious open redirects from redirecting crawler requests to private IPs or cloud metadata.
    """
    if response.is_redirect:
        location = response.headers.get("Location")
        if location:
            target_url = urljoin(str(response.url), location)
            # Validates scheme, port, IP address, hostname, and restricts private IPs/metadata
            validate_and_normalize_url(target_url)


class RebindingSafeAnyIOBackend(AnyIOBackend):
    """
    AnyIO Network backend that validates DNS at connection time and pins the TCP socket
    directly to the verified public IP. Eliminates DNS Rebinding TOCTOU vulnerabilities
    and detects mixed IPv4/IPv6 DNS answers containing restricted IPs.
    """

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Optional[Any] = None,
    ) -> AnyIOStream:
        host_clean = host.strip("[]")
        # Check blocked hostnames and suffixes directly
        if host_clean.lower() in BLOCKED_HOSTNAMES or host_clean.lower() in BLOCKED_IP_STRINGS:
            raise SecurityValidationError(f"Access to restricted host '{host}' blocked at connection time.")

        if host_clean.lower().endswith(BLOCKED_HOST_SUFFIXES):
            raise SecurityValidationError(f"Access to internal domain '{host}' blocked at connection time.")

        # Resolve host at the exact connection instant
        addrinfo = socket.getaddrinfo(host_clean, port, proto=socket.IPPROTO_TCP)
        safe_ip: Optional[str] = None

        # Verify EVERY IP in the answer set (detect mixed DNS answers)
        for family, socktype, proto, canonname, sockaddr in addrinfo:
            ip_str = sockaddr[0]
            if is_ip_private_or_restricted(ip_str) or ip_str in BLOCKED_IP_STRINGS:
                raise SecurityValidationError(
                    f"DNS Rebinding / SSRF blocked: {host} resolved to restricted IP '{ip_str}' at connection time."
                )
            if safe_ip is None:
                safe_ip = ip_str

        target_connect_ip = safe_ip if safe_ip else host_clean

        # Connect directly to the validated IP to pin the TCP socket
        return await super().connect_tcp(
            target_connect_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


class SafeAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    """
    HTTPX transport pre-configured with DNS rebinding defense, connection pinning,
    and ambient proxy bypass (trust_env=False).
    """

    def __init__(self, *args, **kwargs):
        kwargs["trust_env"] = False  # Bypasses ambient HTTP_PROXY/ALL_PROXY variables
        super().__init__(*args, **kwargs)
        # Configure connection pool with rebinding-safe network backend
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=self._pool._ssl_context,
            network_backend=RebindingSafeAnyIOBackend(),
            http1=True,
            http2=False,
        )


def create_safe_client(
    timeout: float = 15.0,
    max_redirects: int = 5,
    headers: Optional[dict[str, str]] = None,
) -> httpx.AsyncClient:
    """
    Create an httpx.AsyncClient pre-configured with:
    - DNS rebinding mitigation (TCP connection pinning to validated IP)
    - SSRF redirect validation hook
    - Ambient proxy bypass (trust_env=False)
    - Strict timeout and redirect limits
    - Respectful User-Agent
    """
    client_headers = {
        "User-Agent": "LeadIntel/0.1 (Business Intelligence Researcher; +https://github.com/example/leadintel; respectful crawler)"
    }
    if headers:
        client_headers.update(headers)

    transport = SafeAsyncHTTPTransport(verify=True)

    return httpx.AsyncClient(
        transport=transport,
        timeout=timeout,
        follow_redirects=True,
        max_redirects=max_redirects,
        trust_env=False,
        event_hooks={"response": [validate_redirect_hook]},
        headers=client_headers,
    )
