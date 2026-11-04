"""
Provider base protocol.

Every data provider must implement BusinessProvider.  Tools import the
registry and call `registry.search(...)` — they never import a specific
provider directly, so swapping or adding providers requires zero tool changes.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models.business import Business


@runtime_checkable
class BusinessProvider(Protocol):
    """Protocol that every LeadIntel data provider must satisfy."""

    #: Human-readable name shown in tool responses and logs
    name: str

    #: True when the provider can be used without any API key or auth
    requires_auth: bool

    async def search(
        self,
        query: str,
        location: str | None,
        category: str | None,
        limit: int,
    ) -> list[Business]:
        """
        Search for businesses.

        Args:
            query:    Free-text keyword.  Pass "*" for a broad sweep.
            location: City / region name or "lat,lon" coordinate string.
            category: Industry hint (e.g. "restaurant", "software").
            limit:    Max results to return.

        Returns:
            List of Business instances, possibly empty.
        """
        ...

    async def get_details(self, business_id: str) -> Business | None:
        """
        Fetch enriched details for a known business ID.

        Returns None if the ID is unknown to this provider.
        """
        ...
