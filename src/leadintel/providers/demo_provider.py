"""
DemoProvider — always-available fallback using synthetic fixture data.

Returns the same 5 sample businesses as Phase 1.  No network required.
"""

from __future__ import annotations

from typing import Any

from ..data.demo import get_demo_business, search_demo_businesses
from ..models.business import Business
from .base import BusinessProvider


class DemoProvider:
    """Synthetic demo data provider.  Zero dependencies, always works."""

    name: str = "demo"
    requires_auth: bool = False

    def __init__(self) -> None:
        self.last_search_center: dict[str, float] | None = None
        self.last_radius_meters: int | None = None

    async def search(
        self,
        query: str,
        location: str | None = None,
        category: str | None = None,
        limit: int = 10,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_meters: int | None = None,
        wider_metro: bool = False,
        **kwargs: Any,
    ) -> list[Business]:
        if latitude is not None and longitude is not None:
            self.last_search_center = {"latitude": float(latitude), "longitude": float(longitude)}
        elif location and "pune" in location.lower():
            self.last_search_center = {"latitude": 18.5204, "longitude": 73.8567}
        self.last_radius_meters = (
            (radius_meters if radius_meters is not None else 25_000)
            if wider_metro
            else (radius_meters if radius_meters is not None else 6_000)
        )

        return search_demo_businesses(
            query=query,
            location=location,
            category=category,
            limit=limit,
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
            wider_metro=wider_metro,
            **kwargs,
        )

    async def get_details(self, business_id: str) -> Business | None:
        return get_demo_business(business_id)


# Satisfy the protocol at import time (structural subtyping check)
_: BusinessProvider = DemoProvider()  # type: ignore[assignment]
