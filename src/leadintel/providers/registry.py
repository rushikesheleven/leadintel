"""
Provider registry — selects and chains providers at runtime.

Priority order (highest → lowest):
  1. OverpassProvider   (free, OSM-backed, requires network)
  2. DemoProvider       (always available, synthetic data)

Future providers (OpenStreetMapNominatim, custom) slot in without touching
any tool code.
"""

from __future__ import annotations

import inspect
import logging
from typing import TYPE_CHECKING, Any

from ..models.business import Business
from .base import BusinessProvider

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Ordered list of providers with automatic fallback."""

    def __init__(self, providers: list[BusinessProvider]) -> None:
        if not providers:
            raise ValueError("ProviderRegistry requires at least one provider.")
        self._providers = providers
        self.last_error: str | None = None
        self.last_search_center: dict[str, float] | None = None
        self.last_radius_meters: int | None = None

    @property
    def primary(self) -> BusinessProvider:
        return self._providers[0]

    @property
    def all_providers(self) -> list[BusinessProvider]:
        return list(self._providers)

    def provider_names(self) -> list[str]:
        return [p.name for p in self._providers]

    async def search(
        self,
        query: str,
        location: str | None = None,
        category: str | None = None,
        limit: int = 10,
        **kwargs: Any,
    ) -> tuple[list[Business], str]:
        """
        Try providers in order, return first non-empty result.

        Returns:
            (businesses, provider_name) — the name of the provider that
            actually returned data.
        """
        self.last_error = None
        self.last_search_center = None
        self.last_radius_meters = None

        for provider in self._providers:
            # If a location or explicit coords were provided for live search, do not fall back to demo data
            has_explicit_loc = bool(location or kwargs.get("latitude") is not None)
            if has_explicit_loc and provider.name == "demo" and len(self._providers) > 1:
                logger.debug(
                    "Skipping DemoProvider for live search with location '%s'.", location
                )
                continue

            try:
                sig = inspect.signature(provider.search)
                if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                    call_kwargs = kwargs
                else:
                    call_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}

                results = await provider.search(
                    query=query,
                    location=location,
                    category=category,
                    limit=limit,
                    **call_kwargs,
                )

                if hasattr(provider, "last_search_center"):
                    self.last_search_center = getattr(provider, "last_search_center", None)
                if hasattr(provider, "last_radius_meters"):
                    self.last_radius_meters = getattr(provider, "last_radius_meters", None)

                if results:
                    logger.debug(
                        "Provider '%s' returned %d result(s).",
                        provider.name,
                        len(results),
                    )
                    return results, provider.name

                # If a live provider successfully executed search and found 0 results for a location,
                # do not fall through to demo data — report 0 live results.
                if has_explicit_loc and provider.name != "demo":
                    logger.debug(
                        "Live provider '%s' returned 0 results for location '%s'.",
                        provider.name,
                        location,
                    )
                    return [], provider.name

                logger.debug("Provider '%s' returned 0 results, trying next.", provider.name)
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)
                logger.warning("Provider '%s' failed: %s", provider.name, exc)
                # In live mode with a location, do not swallow the error into demo data
                if has_explicit_loc and provider.name != "demo":
                    return [], provider.name

        return [], self._providers[-1].name

    async def get_details(
        self, business_id: str
    ) -> tuple[Business | None, str]:
        """
        Try providers in order for a single business lookup.

        Returns:
            (business_or_none, provider_name)
        """
        self.last_error = None
        for provider in self._providers:
            # Route by ID prefix when known
            if business_id.startswith("osm_") and provider.name == "demo":
                continue
            if business_id.startswith("demo_") and provider.name != "demo":
                continue

            try:
                result = await provider.get_details(business_id)
                if result is not None:
                    return result, provider.name
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)
                logger.warning(
                    "Provider '%s' get_details failed: %s", provider.name, exc
                )
        return None, self._providers[-1].name
