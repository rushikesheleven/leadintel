"""
DemoProvider — always-available fallback using synthetic fixture data.

Returns the same 5 sample businesses as Phase 1.  No network required.
"""

from __future__ import annotations

from ..data.demo import get_demo_business, search_demo_businesses
from ..models.business import Business
from .base import BusinessProvider


class DemoProvider:
    """Synthetic demo data provider.  Zero dependencies, always works."""

    name: str = "demo"
    requires_auth: bool = False

    async def search(
        self,
        query: str,
        location: str | None,
        category: str | None,
        limit: int,
    ) -> list[Business]:
        return search_demo_businesses(
            query=query,
            location=location,
            category=category,
            limit=limit,
        )

    async def get_details(self, business_id: str) -> Business | None:
        return get_demo_business(business_id)


# Satisfy the protocol at import time (structural subtyping check)
_: BusinessProvider = DemoProvider()  # type: ignore[assignment]
