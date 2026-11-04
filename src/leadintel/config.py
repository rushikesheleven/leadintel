"""
LeadIntel configuration loaded from environment variables.

Core principle: ZERO mandatory API keys.
All external services are free and optional.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the working directory if present
_env_file = Path.cwd() / ".env"
if _env_file.exists():
    load_dotenv(_env_file)


@dataclass(frozen=True)
class Settings:
    """Immutable configuration object for LeadIntel."""

    # ── Overpass / OpenStreetMap ──────────────────────────────────────────────
    overpass_endpoint: str = field(
        default_factory=lambda: os.environ.get(
            "OVERPASS_ENDPOINT", "https://overpass-api.de/api/interpreter"
        )
    )
    # Search radius in metres around a geocoded point
    overpass_radius_m: int = field(
        default_factory=lambda: int(os.environ.get("OVERPASS_RADIUS_M", "5000"))
    )

    # ── Ollama (optional local AI) ────────────────────────────────────────────
    ollama_enabled: bool = field(
        default_factory=lambda: os.environ.get("OLLAMA_ENABLED", "false").lower()
        in ("true", "1", "yes")
    )
    ollama_base_url: str = field(
        default_factory=lambda: os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    ollama_model: str = field(
        default_factory=lambda: os.environ.get("OLLAMA_MODEL", "llama3")
    )

    # ── Storage ───────────────────────────────────────────────────────────────
    database_path: str = field(
        default_factory=lambda: os.environ.get("LEADINTEL_DB_PATH", "leadintel.db")
    )

    # ── HTTP / cache ──────────────────────────────────────────────────────────
    # In-process result cache TTL in seconds (max 604 800 = 7 days per OSM policy)
    cache_ttl: int = field(
        default_factory=lambda: int(os.environ.get("CACHE_TTL", "3600"))
    )
    # HTTP request timeout for external calls (seconds)
    request_timeout: float = field(
        default_factory=lambda: float(os.environ.get("REQUEST_TIMEOUT", "30.0"))
    )
    # Respect robots.txt during website analysis
    respect_robots: bool = field(
        default_factory=lambda: os.environ.get("RESPECT_ROBOTS", "true").lower()
        not in ("false", "0", "no")
    )

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = field(
        default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO")
    )

    # ── Demo mode ─────────────────────────────────────────────────────────────
    # When True, the DemoProvider is the ONLY provider (no network calls).
    # When False, live providers (Overpass, etc.) are tried first with demo fallback.
    demo_mode: bool = field(
        default_factory=lambda: os.environ.get("DEMO_MODE", "false").lower()
        in ("true", "1", "yes")
    )

    # ── Legacy / optional third-party keys (kept for future providers) ────────
    # These are never required; presence enables richer optional features.
    google_places_api_key: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_PLACES_API_KEY", ""),
        repr=False,
    )
    pagespeed_api_key: str = field(
        default_factory=lambda: os.environ.get("PAGESPEED_API_KEY", ""),
        repr=False,
    )
    gemini_api_key: str = field(
        default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""),
        repr=False,
    )

    def __repr__(self) -> str:
        """Safe string representation masking all sensitive tokens."""
        return f"Settings({self.safe_dict()})"

    # ── Derived properties ────────────────────────────────────────────────────

    @property
    def has_ollama(self) -> bool:
        return self.ollama_enabled

    @property
    def has_google_places(self) -> bool:
        return bool(self.google_places_api_key)

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    def safe_dict(self) -> dict:
        """Return config as dict with secrets redacted (safe for logging)."""
        return {
            "overpass_endpoint": self.overpass_endpoint,
            "overpass_radius_m": self.overpass_radius_m,
            "ollama_enabled": self.ollama_enabled,
            "ollama_base_url": self.ollama_base_url,
            "ollama_model": self.ollama_model,
            "database_path": self.database_path,
            "cache_ttl": self.cache_ttl,
            "request_timeout": self.request_timeout,
            "respect_robots": self.respect_robots,
            "log_level": self.log_level,
            "demo_mode": self.demo_mode,
            # Third-party keys — never log the actual value
            "google_places_api_key": "***" if self.google_places_api_key else "(not set)",
            "pagespeed_api_key": "***" if self.pagespeed_api_key else "(not set)",
            "gemini_api_key": "***" if self.gemini_api_key else "(not set)",
        }


# Module-level singleton imported throughout the codebase
settings = Settings()
