"""MCP tool: search_businesses — powered by the provider registry and website opportunity engine."""

from __future__ import annotations

import logging
from typing import Optional

from mcp.server.mcpserver import MCPServer

from ..config import settings
from ..models.business import Business, BusinessSearchResult
from ..providers import build_registry
from ..services.website_opportunity import batch_evaluate_websites
from ..storage.db import save_businesses

logger = logging.getLogger(__name__)

OSM_ATTRIBUTION = "Data © OpenStreetMap contributors, ODbL 1.0 — https://www.openstreetmap.org/copyright"

_registry = build_registry(settings)


def _compute_data_confidence(b: Business) -> float:
    """Calculate an evidence-based confidence indicator (0.0 to 1.0) for a business record."""
    points = 0.0
    # Location certainty
    if b.latitude is not None and b.longitude is not None:
        points += 0.25
    elif b.address:
        points += 0.15

    # Category classification
    if b.category:
        points += 0.20

    # Contact accessibility
    if b.phone:
        points += 0.15
    if b.email:
        points += 0.10

    # Website verification completeness
    if b.website_status in ("website_verified", "website_not_found_after_research", "website_broken"):
        points += 0.20
    elif b.website_status == "website_unverified":
        points += 0.10

    # OpenStreetMap provenance
    if b.osm_tags:
        points += 0.10

    return round(min(1.0, max(0.2, points)), 2)


def _apply_ranking(
    businesses: list[Business],
    sort_by: str,
) -> list[Business]:
    """Sort businesses by selected criterion and generate ranking_explanation for each."""
    sort_strategy = (sort_by or "highest_website_opportunity").lower().strip()

    if sort_strategy == "closest":
        businesses.sort(
            key=lambda b: (
                b.distance_meters if b.distance_meters is not None else 999_999_999,
                -(b.website_opportunity_score or 0.0),
            )
        )
    elif sort_strategy == "highest_lead_score":
        # Score based on commercial visibility and review count
        businesses.sort(
            key=lambda b: (
                -(b.review_count or 0),
                -(b.rating or 0.0),
                b.distance_meters if b.distance_meters is not None else 999_999,
            )
        )
    elif sort_strategy == "best_seo_opportunity":
        businesses.sort(
            key=lambda b: (
                -(b.website_opportunity_score or 0.0),
                b.distance_meters if b.distance_meters is not None else 999_999,
            )
        )
    else:
        # Default: highest_website_opportunity
        # Prioritize:
        # 1. No website found after research (90-100)
        # 2. Broken websites (75-89)
        # 3. Weak / outdated websites (50-74)
        # 4. Significant SEO problems (30-49)
        # 5. Good websites (5-29)
        # Tie-breaker: distance to search center
        businesses.sort(
            key=lambda b: (
                -(b.website_opportunity_score if b.website_opportunity_score is not None else -1.0),
                b.distance_meters if b.distance_meters is not None else 999_999_999,
                -(b.data_confidence or 0.0),
            )
        )

    # Populate ranking_explanation
    for idx, b in enumerate(businesses, 1):
        dist_str = f"{b.distance_km} km away" if b.distance_km is not None else "distance uncalculated"
        opp_score_str = (
            f"Opportunity score: {b.website_opportunity_score:.1f}/100"
            if b.website_opportunity_score is not None
            else "Opportunity unassessed"
        )

        if b.website_status == "website_not_found_after_research":
            explanation = (
                f"Ranked #{idx}: High-priority web development opportunity. "
                f"No official website found after thorough web research ({opp_score_str}, {dist_str})."
            )
        elif b.website_status == "website_broken":
            explanation = (
                f"Ranked #{idx}: Broken website detected ({opp_score_str}, {dist_str}). "
                f"Immediate redesign or technical repair required."
            )
        elif b.website_status == "website_unverified":
            explanation = (
                f"Ranked #{idx}: Unverified website ({opp_score_str}, {dist_str}). "
                f"Domain cannot be reliably matched to the business name."
            )
        elif b.website_status == "website_verified":
            if (b.website_opportunity_score or 0) >= 50:
                explanation = (
                    f"Ranked #{idx}: Outdated website presence ({opp_score_str}, {dist_str}). "
                    f"Active site lacks mobile responsiveness or HTTPS encryption."
                )
            elif (b.website_opportunity_score or 0) >= 30:
                explanation = (
                    f"Ranked #{idx}: Active website with SEO/performance deficiencies ({opp_score_str}, {dist_str})."
                )
            else:
                explanation = (
                    f"Ranked #{idx}: Established digital presence ({opp_score_str}, {dist_str}). "
                    f"Fast, secure, and mobile-friendly."
                )
        else:
            explanation = (
                f"Ranked #{idx}: Website uninspected ({opp_score_str}, {dist_str})."
            )

        b.ranking_explanation = explanation

    return businesses


def register(mcp: MCPServer) -> None:
    """Register search_businesses tool on the MCP server."""

    @mcp.tool()
    async def search_businesses(
        query: str,
        location: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_meters: Optional[int] = None,
        sort_by: Optional[str] = "highest_website_opportunity",
        research_websites: bool = True,
        wider_metro: bool = False,
    ) -> dict:
        """
        Search for local businesses and identify high-value website development opportunities.

        Features:
        - Geographic precision: strictly limits searches to the requested radius around city/coords.
        - Distance calculation: provides exact distance from search centre for every business.
        - Website opportunity intelligence: researches missing websites, verifies domain ownership,
          detects broken sites, and scores web dev opportunity (0–100 scale).
        - Multi-criteria ranking: prioritizes businesses without websites by default.

        Args:
            query:              Free-text search term, e.g. "coffee shop", "restaurants",
                                "law firm", "software". Pass "*" for a broad sweep.
            location:           City, neighbourhood, or "lat,lon" coordinates, e.g. "Pune",
                                "Shivajinagar, Pune", "London", "Austin, TX".
            category:           Optional industry hint, e.g. "Food & Beverage", "Technology",
                                "Healthcare". Narrows OSM tag filters.
            limit:              Maximum results to return (1–50, default 10).
            latitude:           Optional explicit latitude coordinate to center the search.
            longitude:          Optional explicit longitude coordinate to center the search.
            radius_meters:      Configurable search radius in metres (default: 6000m / 6km).
            sort_by:            Ranking criterion: 'highest_website_opportunity' (default),
                                'closest', 'highest_lead_score', 'best_seo_opportunity'.
            research_websites:  If True (default), performs web research on businesses missing
                                an OSM website to verify if they genuinely lack an official site.
            wider_metro:        If True, expands search radius to metropolitan boundaries (25km)
                                instead of strictly limiting to the urban core.

        Returns:
            dict containing:
              query, location, category, search_center, radius_meters, sort_by
              total_found (int)
              businesses (list[dict]):
                - name, category, address, phone, email, website
                - distance_meters, distance_km
                - website_status ('website_verified', 'website_not_found_after_research',
                                  'website_unverified', 'website_broken', 'website_not_checked')
                - website_opportunity_score (0–100)
                - website_opportunity_explanation
                - data_confidence (0.0–1.0)
                - ranking_explanation
                - osm_tags
              provider, attribution, retrieved_at, note, error
        """
        limit = max(1, min(limit, 50))

        raw_businesses, provider_name = await _registry.search(
            query=query,
            location=location,
            category=category,
            limit=limit,
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
            wider_metro=wider_metro,
        )

        is_osm = provider_name == "openstreetmap"
        is_demo = provider_name == "demo"

        # 1. Evaluate website opportunity and verify presence
        evaluated_businesses = await batch_evaluate_websites(
            businesses=raw_businesses,
            location=location,
            research_missing=research_websites,
            max_concurrent=5,
        )

        # 2. Compute data confidence for each record
        for b in evaluated_businesses:
            b.data_confidence = _compute_data_confidence(b)

        # 3. Apply multi-criteria ranking and populate explanations
        ranked_businesses = _apply_ranking(
            businesses=evaluated_businesses,
            sort_by=sort_by or "highest_website_opportunity",
        )

        note: Optional[str] = None
        error: Optional[str] = None

        if is_demo:
            note = (
                "ℹ️ Demo data returned. "
                "Provide a 'location' parameter to enable live OpenStreetMap search "
                "(no API key required)."
            )
        elif is_osm:
            if getattr(_registry, "last_error", None):
                error = _registry.last_error
                note = f"⚠️ OpenStreetMap live search encountered an issue: {_registry.last_error}"
            elif len(ranked_businesses) == 0:
                note = f"No businesses found matching your criteria in OpenStreetMap near '{location}'."
            else:
                note = (
                    f"✅ Live data from OpenStreetMap with website opportunity intelligence. "
                    f"Attribution required: {OSM_ATTRIBUTION}"
                )

        result = BusinessSearchResult(
            query=query,
            location=location,
            category=category,
            search_center=_registry.last_search_center,
            radius_meters=_registry.last_radius_meters,
            sort_by=sort_by or "highest_website_opportunity",
            total_found=len(ranked_businesses),
            businesses=ranked_businesses,
            source=provider_name,
            provider=provider_name,
            attribution=OSM_ATTRIBUTION if is_osm else None,
            note=note,
            error=error,
        )

        # Save researched businesses into SQLite persistence
        save_businesses(ranked_businesses)

        return result.model_dump(mode="json")
