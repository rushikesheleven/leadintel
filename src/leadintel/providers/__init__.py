"""
Providers package — exports the registry factory and all providers.

Usage:
    from leadintel.providers import build_registry

    registry = build_registry(settings)
    businesses, source = await registry.search(...)
"""

from __future__ import annotations

from ..config import Settings
from .base import BusinessProvider
from .demo_provider import DemoProvider
from .overpass_provider import OverpassProvider
from .registry import ProviderRegistry


def build_registry(cfg: Settings) -> ProviderRegistry:
    """
    Construct the provider registry from application settings.

    Providers are listed in priority order (first = highest priority).
    DemoProvider is always appended last as a guaranteed fallback.
    """
    providers: list[BusinessProvider] = []  # type: ignore[type-arg]

    if not cfg.demo_mode:
        # Live providers — ordered by reliability and data quality
        providers.append(
            OverpassProvider(
                endpoint=cfg.overpass_endpoint,
                radius_m=cfg.overpass_radius_m,
                cache_ttl=cfg.cache_ttl,
            )
        )

    # Demo is always last so the server works with zero configuration
    providers.append(DemoProvider())  # type: ignore[arg-type]

    return ProviderRegistry(providers)


__all__ = [
    "BusinessProvider",
    "DemoProvider",
    "OverpassProvider",
    "ProviderRegistry",
    "build_registry",
]
