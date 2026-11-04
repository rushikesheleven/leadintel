"""
Provider registry — selects and chains providers at runtime.

Priority order (highest → lowest):
  1. OverpassProvider   (free, OSM-backed, requires network)
  2. DemoProvider       (always available, synthetic data)

Future providers (OpenStreetMapNominatim, custom) slot in without touching
any tool code.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

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
        location: str | None,
        category: str | None,
        limit: int,
    ) -> tuple[list[Business], str]:
        """
        Try providers in order, return first non-empty result.

        Returns:
            (businesses, provider_name) — the name of the provider that
            actually returned data.
        """
        for provider in self._providers:
            try:
                results = await provider.search(
                    query=query,
                    location=location,
                    category=category,
                    limit=limit,
                )
                if results:
                    logger.debug(
                        "Provider '%s' returned %d result(s).",
                        provider.name,
                        len(results),
                    )
                    return results, provider.name
                logger.debug("Provider '%s' returned 0 results, trying next.", provider.name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Provider '%s' failed: %s", provider.name, exc)

        return [], self._providers[-1].name

    async def get_details(
        self, business_id: str
    ) -> tuple[Business | None, str]:
        """
        Try providers in order for a single business lookup.

        Returns:
            (business_or_none, provider_name)
        """
        for provider in self._providers:
            try:
                result = await provider.get_details(business_id)
                if result is not None:
                    return result, provider.name
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Provider '%s' get_details failed: %s", provider.name, exc
                )
        return None, self._providers[-1].name
