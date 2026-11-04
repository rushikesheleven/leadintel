"""
OverpassProvider — free business discovery via OpenStreetMap Overpass API.

Attribution requirement (ODbL):
    Data © OpenStreetMap contributors, ODbL 1.0.
    https://www.openstreetmap.org/copyright

Usage policy:
    - Rate-limit: ≤1 req/s; do not hammer the public endpoint.
    - Use the public endpoint: https://overpass-api.de/api/interpreter
      or a self-hosted instance (set OVERPASS_ENDPOINT env var).
    - Never cache results longer than 7 days to honour OSM data freshness.
    - Always display the ODbL attribution string in exports.

This provider:
    * Geocodes location strings via Nominatim (also free, ODbL).
    * Queries Overpass QL for named businesses in a bounding box.
    * Maps OSM tags → Business model fields.
    * Implements a simple in-process TTL cache to avoid hammering the API.
    * Falls back to demo data (handled by the registry) on any error.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any
from urllib.parse import quote

import httpx

from ..models.business import Business

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
NOMINATIM_ENDPOINT = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_ENDPOINT = "https://nominatim.openstreetmap.org/reverse"
OSM_ATTRIBUTION = "Data © OpenStreetMap contributors, ODbL 1.0"
USER_AGENT = "LeadIntel/0.1 (open-source MCP server; github.com/example/leadintel)"

# Default search radius around a geocoded point, in metres
DEFAULT_RADIUS_M = 5_000
# Max radius to keep queries fast
MAX_RADIUS_M = 50_000
# Overpass request timeout (seconds)
REQUEST_TIMEOUT = 30.0
# Minimum seconds between consecutive Overpass requests (rate-limit)
MIN_REQUEST_INTERVAL = 1.1
# Simple in-process cache TTL (seconds); never exceed 7 days (604 800 s)
CACHE_TTL = 3_600  # 1 hour


# ── OSM tag → category mapping ────────────────────────────────────────────────
_OSM_AMENITY_TO_CATEGORY: dict[str, str] = {
    "restaurant": "Food & Beverage",
    "cafe": "Food & Beverage",
    "bar": "Food & Beverage",
    "pub": "Food & Beverage",
    "fast_food": "Food & Beverage",
    "hospital": "Healthcare",
    "clinic": "Healthcare",
    "pharmacy": "Healthcare",
    "dentist": "Healthcare",
    "school": "Education",
    "university": "Education",
    "college": "Education",
    "bank": "Financial Services",
    "atm": "Financial Services",
    "hotel": "Hospitality",
    "hostel": "Hospitality",
    "guest_house": "Hospitality",
    "gym": "Health & Fitness",
    "fuel": "Automotive",
    "car_wash": "Automotive",
    "cinema": "Entertainment",
    "theatre": "Entertainment",
    "library": "Education",
    "post_office": "Government Services",
    "police": "Government Services",
    "fire_station": "Government Services",
    "place_of_worship": "Religion",
    "marketplace": "Retail",
    "supermarket": "Retail",
    "convenience": "Retail",
    "hairdresser": "Personal Care",
    "beauty": "Personal Care",
    "laundry": "Personal Care",
    "shop": "Retail",
    "office": "Professional Services",
    "coworking_space": "Professional Services",
    "it": "Technology",
    "accountant": "Professional Services",
    "lawyer": "Legal Services",
    "estate_agent": "Real Estate",
    "travel_agency": "Travel",
    "car_rental": "Automotive",
    "charging_station": "Automotive",
}

_OSM_SHOP_TO_CATEGORY: dict[str, str] = {
    "supermarket": "Retail – Grocery",
    "clothes": "Retail – Fashion",
    "electronics": "Retail – Electronics",
    "furniture": "Retail – Furniture",
    "hardware": "Retail – Hardware",
    "bakery": "Food & Beverage",
    "butcher": "Food & Beverage",
    "florist": "Retail – Florist",
    "books": "Retail – Books",
    "sports": "Retail – Sports",
    "jewelry": "Retail – Jewellery",
    "computer": "Technology",
    "mobile_phone": "Technology",
    "car": "Automotive – Dealer",
    "bicycle": "Retail – Bicycle",
    "optician": "Healthcare – Optician",
    "chemist": "Healthcare – Pharmacy",
}

_OSM_OFFICE_TO_CATEGORY: dict[str, str] = {
    "it": "Technology",
    "software": "Technology",
    "company": "Professional Services",
    "consulting": "Consulting",
    "lawyer": "Legal Services",
    "accountant": "Accounting",
    "architect": "Architecture",
    "engineer": "Engineering",
    "financial": "Financial Services",
    "insurance": "Insurance",
    "marketing": "Marketing",
    "advertising": "Marketing",
    "real_estate": "Real Estate",
    "travel_agent": "Travel",
    "government": "Government",
    "ngo": "Non-Profit",
}


def _osm_tags_to_category(tags: dict[str, str]) -> str | None:
    amenity = tags.get("amenity", "")
    shop = tags.get("shop", "")
    office = tags.get("office", "")

    if amenity:
        return _OSM_AMENITY_TO_CATEGORY.get(amenity, amenity.replace("_", " ").title())
    if shop:
        return _OSM_SHOP_TO_CATEGORY.get(shop, shop.replace("_", " ").title())
    if office:
        return _OSM_OFFICE_TO_CATEGORY.get(office, office.replace("_", " ").title())

    craft = tags.get("craft", "")
    if craft:
        return craft.replace("_", " ").title()

    tourism = tags.get("tourism", "")
    if tourism:
        return tourism.replace("_", " ").title()

    healthcare = tags.get("healthcare", "")
    if healthcare:
        return "Healthcare"

    leisure = tags.get("leisure", "")
    if leisure:
        return leisure.replace("_", " ").title()

    return None


def _osm_element_to_business(element: dict[str, Any]) -> Business | None:
    """Convert a raw Overpass API element to a Business.  Returns None if unusable."""
    tags: dict[str, str] = element.get("tags", {})

    name = tags.get("name") or tags.get("brand") or tags.get("operator")
    if not name:
        return None

    # Coordinates — node has lat/lon directly; way/relation use centre
    if element["type"] == "node":
        lat = element.get("lat")
        lon = element.get("lon")
    else:
        centre = element.get("center", {})
        lat = centre.get("lat")
        lon = centre.get("lon")

    osm_id = f"osm_{element['type']}_{element['id']}"

    # Address
    addr_parts = [
        tags.get("addr:housenumber", ""),
        tags.get("addr:street", ""),
    ]
    street = " ".join(p for p in addr_parts if p).strip()
    city = tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village")
    state = tags.get("addr:state") or tags.get("addr:province")
    country = tags.get("addr:country")
    postal_code = tags.get("addr:postcode")

    address_parts = [p for p in [street, city, state, postal_code, country] if p]
    address = ", ".join(address_parts) if address_parts else None

    return Business(
        id=osm_id,
        name=name,
        category=_osm_tags_to_category(tags),
        address=address,
        city=city,
        state=state,
        country=country,
        postal_code=postal_code,
        latitude=lat,
        longitude=lon,
        phone=tags.get("phone") or tags.get("contact:phone"),
        email=tags.get("email") or tags.get("contact:email"),
        website=tags.get("website") or tags.get("contact:website") or tags.get("url"),
        source="openstreetmap",
        is_ai_generated=False,
    )


def _cache_key(query: str, location: str | None, category: str | None, limit: int) -> str:
    raw = json.dumps(
        {"q": query, "loc": location, "cat": category, "lim": limit},
        sort_keys=True,
    )
    return hashlib.md5(raw.encode()).hexdigest()  # noqa: S324 — non-crypto use


class OverpassProvider:
    """
    Business discovery via the free Overpass API (OpenStreetMap data).

    Attributes:
        name:         Provider identifier shown in responses.
        requires_auth: False — no API key needed.
        endpoint:     Overpass interpreter URL (default: public instance).
        radius_m:     Search radius in metres around a geocoded location.
    """

    name: str = "openstreetmap"
    requires_auth: bool = False

    def __init__(
        self,
        endpoint: str = OVERPASS_ENDPOINT,
        radius_m: int = DEFAULT_RADIUS_M,
        cache_ttl: int = CACHE_TTL,
    ) -> None:
        self.endpoint = endpoint
        self.radius_m = min(radius_m, MAX_RADIUS_M)
        self._cache: dict[str, tuple[float, list[Business]]] = {}
        self._cache_ttl = cache_ttl
        self._last_request: float = 0.0

    # ── Public interface ──────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        location: str | None,
        category: str | None,
        limit: int,
    ) -> list[Business]:
        """Search OSM for businesses matching the query near the location."""
        key = _cache_key(query, location, category, limit)
        cached = self._get_cache(key)
        if cached is not None:
            logger.debug("Cache hit for key %s", key)
            return cached

        bbox = await self._resolve_bbox(location)
        if bbox is None:
            logger.warning("Could not geocode location '%s'; skipping OSM search.", location)
            return []

        businesses = await self._run_overpass(query=query, category=category, bbox=bbox, limit=limit)
        self._set_cache(key, businesses)
        return businesses

    async def get_details(self, business_id: str) -> Business | None:
        """Look up a single OSM element by its leadintel ID (osm_<type>_<id>)."""
        if not business_id.startswith("osm_"):
            return None
        parts = business_id.split("_", 2)
        if len(parts) != 3:
            return None
        _, osm_type, osm_id_str = parts
        try:
            osm_id = int(osm_id_str)
        except ValueError:
            return None

        query = f"""
[out:json][timeout:15];
{osm_type}({osm_id});
out body center;
"""
        data = await self._post_overpass(query)
        elements = data.get("elements", [])
        if not elements:
            return None
        return _osm_element_to_business(elements[0])

    # ── Geocoding ─────────────────────────────────────────────────────────────

    async def _resolve_bbox(
        self, location: str | None
    ) -> tuple[float, float, float, float] | None:
        """Return (south, west, north, east) bounding box for a location string."""
        if not location:
            # No location → world-wide search is too broad; signal caller
            return None

        # Accept raw "lat,lon" coordinates
        if "," in location and all(
            p.strip().replace("-", "").replace(".", "").isdigit()
            for p in location.split(",", 1)
        ):
            try:
                lat, lon = (float(p.strip()) for p in location.split(",", 1))
                return self._bbox_around(lat, lon)
            except ValueError:
                pass

        # Geocode via Nominatim
        params = {
            "q": location,
            "format": "json",
            "limit": "1",
        }
        headers = {"User-Agent": USER_AGENT}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                await self._rate_limit()
                resp = await client.get(NOMINATIM_ENDPOINT, params=params, headers=headers)
                resp.raise_for_status()
                results = resp.json()

            if not results:
                return None

            top = results[0]
            # Prefer the OSM-provided bounding box if available
            bb = top.get("boundingbox")
            if bb and len(bb) == 4:
                s, n, w, e = float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])
                return s, w, n, e

            lat = float(top["lat"])
            lon = float(top["lon"])
            return self._bbox_around(lat, lon)

        except Exception as exc:
            logger.warning("Nominatim geocoding failed for '%s': %s", location, exc)
            return None

    def _bbox_around(
        self, lat: float, lon: float
    ) -> tuple[float, float, float, float]:
        """Create a square bounding box of self.radius_m around (lat, lon)."""
        delta_lat = self.radius_m / 111_320
        delta_lon = self.radius_m / (111_320 * abs(__import__("math").cos(__import__("math").radians(lat))) or 1)
        return (
            lat - delta_lat,
            lon - delta_lon,
            lat + delta_lat,
            lon + delta_lon,
        )

    # ── Overpass query builder ────────────────────────────────────────────────

    def _build_overpass_query(
        self,
        query: str,
        category: str | None,
        bbox: tuple[float, float, float, float],
        limit: int,
    ) -> str:
        """Generate an Overpass QL query for the given parameters."""
        s, w, n, e = bbox
        bbox_str = f"{s},{w},{n},{e}"

        # Determine which OSM tags to filter on
        filters = self._build_tag_filters(query=query, category=category)

        # Build union of node + way + relation for each filter
        union_parts: list[str] = []
        for f in filters:
            for element_type in ("node", "way", "relation"):
                union_parts.append(f'{element_type}{f}({bbox_str});')

        union_block = "\n  ".join(union_parts)

        return f"""
[out:json][timeout:{int(REQUEST_TIMEOUT)}];
(
  {union_block}
);
out body center {limit * 3};
""".strip()

    @staticmethod
    def _build_tag_filters(query: str, category: str | None) -> list[str]:
        """
        Map the free-text query + category to Overpass tag filter strings.

        Returns a list of filter strings like ['["amenity"="restaurant"]',
        '["shop"="bakery"]'] that are interpolated directly into QL.
        """
        q = (query or "").lower().strip()
        cat = (category or "").lower().strip()
        combined = f"{q} {cat}".strip()

        # Direct keyword → OSM tag mappings
        _KEYWORD_MAP: list[tuple[str, str]] = [
            ("restaurant", '["amenity"="restaurant"]'),
            ("cafe", '["amenity"="cafe"]'),
            ("coffee", '["amenity"="cafe"]'),
            ("bar", '["amenity"="bar"]'),
            ("pub", '["amenity"="pub"]'),
            ("fast food", '["amenity"="fast_food"]'),
            ("hotel", '["tourism"="hotel"]'),
            ("hostel", '["tourism"="hostel"]'),
            ("bank", '["amenity"="bank"]'),
            ("atm", '["amenity"="atm"]'),
            ("hospital", '["amenity"="hospital"]'),
            ("clinic", '["amenity"="clinic"]'),
            ("pharmacy", '["amenity"="pharmacy"]'),
            ("dentist", '["amenity"="dentist"]'),
            ("school", '["amenity"="school"]'),
            ("university", '["amenity"="university"]'),
            ("gym", '["leisure"="fitness_centre"]'),
            ("fitness", '["leisure"="fitness_centre"]'),
            ("supermarket", '["shop"="supermarket"]'),
            ("grocery", '["shop"="supermarket"]'),
            ("clothes", '["shop"="clothes"]'),
            ("fashion", '["shop"="clothes"]'),
            ("electronics", '["shop"="electronics"]'),
            ("technology", '["office"="it"]'),
            ("software", '["office"="software"]'),
            ("consulting", '["office"="consulting"]'),
            ("law", '["office"="lawyer"]'),
            ("lawyer", '["office"="lawyer"]'),
            ("accountant", '["office"="accountant"]'),
            ("real estate", '["office"="real_estate"]'),
            ("estate agent", '["office"="estate_agent"]'),
            ("marketing", '["office"="marketing"]'),
            ("advertising", '["office"="advertising"]'),
            ("coworking", '["amenity"="coworking_space"]'),
            ("fuel", '["amenity"="fuel"]'),
            ("petrol", '["amenity"="fuel"]'),
            ("gas station", '["amenity"="fuel"]'),
            ("cinema", '["amenity"="cinema"]'),
            ("theatre", '["amenity"="theatre"]'),
            ("travel", '["office"="travel_agent"]'),
            ("hair", '["shop"="hairdresser"]'),
            ("salon", '["shop"="beauty"]'),
            ("beauty", '["shop"="beauty"]'),
            ("ngo", '["office"="ngo"]'),
            ("nonprofit", '["office"="ngo"]'),
            ("food", '["amenity"~"restaurant|cafe|fast_food|bar"]'),
            ("shop", '["shop"]'),
            ("office", '["office"]'),
            ("business", '["name"]'),
        ]

        # Try to find a specific match first
        for keyword, tag_filter in _KEYWORD_MAP:
            if keyword in combined:
                return [tag_filter]

        # Wildcard / generic — return anything with a name tag
        if q in ("*", "", "all", "any"):
            return ['["name"]']

        # Fall back: name substring search (slow but correct for arbitrary queries)
        safe_q = query.replace('"', "").replace("\\", "")
        return [f'["name"~"{safe_q}",i]']


    # ── HTTP helpers ──────────────────────────────────────────────────────────

    async def _run_overpass(
        self,
        query: str,
        category: str | None,
        bbox: tuple[float, float, float, float],
        limit: int,
    ) -> list[Business]:
        overpass_query = self._build_overpass_query(
            query=query, category=category, bbox=bbox, limit=limit
        )
        data = await self._post_overpass(overpass_query)
        elements = data.get("elements", [])

        businesses: list[Business] = []
        seen_names: set[str] = set()

        for element in elements:
            biz = _osm_element_to_business(element)
            if biz is None:
                continue
            # Deduplicate by name+city within a single query
            dedup_key = (biz.name.lower(), (biz.city or "").lower())
            if dedup_key in seen_names:
                continue
            seen_names.add(dedup_key)
            businesses.append(biz)
            if len(businesses) >= limit:
                break

        return businesses

    async def _post_overpass(self, query: str) -> dict:
        """POST a query to the Overpass API and return parsed JSON."""
        await self._rate_limit()
        headers = {"User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"}

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(
                self.endpoint,
                content=f"data={quote(query)}",
                headers=headers,
            )
            resp.raise_for_status()
            self._last_request = time.monotonic()
            return resp.json()

    async def _rate_limit(self) -> None:
        """Sleep if needed to respect the minimum request interval."""
        elapsed = time.monotonic() - self._last_request
        if elapsed < MIN_REQUEST_INTERVAL:
            await asyncio.sleep(MIN_REQUEST_INTERVAL - elapsed)

    # ── Cache ─────────────────────────────────────────────────────────────────

    def _get_cache(self, key: str) -> list[Business] | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        ts, data = entry
        if time.monotonic() - ts > self._cache_ttl:
            del self._cache[key]
            return None
        return data

    def _set_cache(self, key: str, data: list[Business]) -> None:
        self._cache[key] = (time.monotonic(), data)

    def clear_cache(self) -> None:
        self._cache.clear()
