"""
Competitor Research Service.

Identifies potential competitors using:
1. OpenStreetMap (Overpass API / provider registry).
2. Category and industry semantic overlap scoring (distinguishing direct vs indirect competitors).
3. Digital presence analysis (reusing website_analyzer and seo_auditor).
4. Explicit confidence scoring and qualification explanations.

Compliance & Ethics:
- Reuses existing OverpassProvider, respects ODbL attribution.
- Enforces request throttling and SSRF protections.
- Never fabricates competitor facts or ratings.
- Transparently distinguishes verified data from estimated competitive relevance.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..config import settings
from ..models.business import Business
from ..providers import build_registry
from .website_analyzer import analyze_target_website

logger = logging.getLogger(__name__)

_registry = build_registry(settings)

# High-level category grouping for semantic relatedness
CATEGORY_GROUPS: dict[str, set[str]] = {
    "food_dining": {
        "restaurant", "cafe", "coffee", "bakery", "bar", "pub", "fast food",
        "food & beverage", "bistro", "diner", "pizzeria"
    },
    "technology": {
        "software development", "technology", "it", "cloud computing",
        "web design", "information technology", "saas", "consulting"
    },
    "marketing": {
        "digital marketing", "marketing", "advertising", "seo",
        "social media", "public relations", "media agency"
    },
    "professional_services": {
        "management consulting", "consulting", "accounting", "legal services",
        "lawyer", "human resources", "real estate", "recruitment"
    },
    "healthcare": {
        "hospital", "clinic", "pharmacy", "dentist", "healthcare",
        "medical", "optician", "wellness"
    },
    "retail": {
        "retail", "supermarket", "grocery", "clothing", "fashion",
        "electronics", "furniture", "store"
    },
    "fitness": {
        "gym", "fitness", "health & fitness", "yoga", "pilates", "sports"
    },
}


def _tokenize(text: Optional[str]) -> set[str]:
    """Extract normalized lowercase alphanumeric tokens."""
    if not text:
        return set()
    import re
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    stopwords = {"and", "or", "the", "a", "an", "in", "of", "for", "llc", "inc", "ltd", "corp", "co", "services", "solutions", "group"}
    return {t for t in tokens if t not in stopwords}


def calculate_competitor_relevance(
    target_name: str,
    target_category: Optional[str],
    candidate_name: str,
    candidate_category: Optional[str],
) -> tuple[float, str, str]:
    """
    Score competitive relevance between target and candidate business.

    Returns:
        (confidence_score: float (0.0-1.0),
         competitor_type: "direct" | "indirect" | "unrelated",
         qualification_reason: str)
    """
    # Exclude identical business
    if target_name.strip().lower() == candidate_name.strip().lower():
        return 0.0, "unrelated", "Identical business entity."

    t_cat_tokens = _tokenize(target_category)
    c_cat_tokens = _tokenize(candidate_category)

    # 1. Exact or high category overlap
    if t_cat_tokens and c_cat_tokens:
        overlap = t_cat_tokens.intersection(c_cat_tokens)
        if overlap:
            confidence = min(0.95, 0.6 + (0.15 * len(overlap)))
            reason = (
                f"Direct category alignment: shared specialization in "
                f"'{', '.join(sorted(overlap))}'."
            )
            return confidence, "direct", reason

    # 2. Check cluster / group overlap
    target_groups = set()
    candidate_groups = set()
    t_cat_str = (target_category or "").lower()
    c_cat_str = (candidate_category or "").lower()

    for group_name, members in CATEGORY_GROUPS.items():
        if any(m in t_cat_str for m in members):
            target_groups.add(group_name)
        if any(m in c_cat_str for m in members):
            candidate_groups.add(group_name)

    common_groups = target_groups.intersection(candidate_groups)
    if common_groups:
        group_desc = sorted(common_groups)[0].replace("_", " ").title()
        return (
            0.65,
            "indirect",
            f"Indirect competitor in the broader {group_desc} industry, offering related services.",
        )

    # 3. Check name tokens overlap if category is absent or inconclusive
    t_name_tokens = _tokenize(target_name)
    c_name_tokens = _tokenize(candidate_name)
    name_overlap = t_name_tokens.intersection(c_name_tokens)
    if name_overlap and (not target_category or not candidate_category):
        return (
            0.50,
            "indirect",
            f"Possible competitor based on name keywords '{', '.join(sorted(name_overlap))}', though categories differ or are unspecified.",
        )

    # 4. Fallback: unrelated
    return (
        0.10,
        "unrelated",
        "Different industry focus with no significant service or category overlap.",
    )


async def find_industry_competitors(
    business_name: str,
    business_category: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    country: Optional[str] = None,
    website: Optional[str] = None,
    max_competitors: int = 5,
    enrich_websites: bool = True,
) -> dict[str, Any]:
    """
    Search OpenStreetMap and provider registry for relevant competitors,
    classify them as direct or indirect, and optionally evaluate their digital health.
    """
    if not business_name or not business_name.strip():
        raise ValueError("business_name must be a non-empty string.")

    max_competitors = max(1, min(max_competitors, 20))

    # Construct geographic location search string
    location_parts = [p for p in (city, state, country) if p and p.strip()]
    location_str = ", ".join(location_parts) if location_parts else None

    # Search query: prioritize category if given, otherwise business name keywords
    search_term = business_category if (business_category and business_category.strip()) else business_name

    candidates: list[Business] = []
    source_provider = "demo"

    # Query provider registry (Overpass / OSM first, fallback to demo)
    try:
        raw_results, source_provider = await _registry.search(
            query=search_term,
            location=location_str,
            category=business_category,
            limit=max_competitors * 4,  # Overfetch to filter unrelated & self
        )
        candidates.extend(raw_results)
    except Exception as exc:
        logger.warning("Provider registry search failed during competitor lookup: %s", exc)

    # If category search was empty, retry with general category keyword or location
    if not candidates and business_category and location_str:
        try:
            raw_results, source_provider = await _registry.search(
                query="*",
                location=location_str,
                category=business_category,
                limit=max_competitors * 4,
            )
            candidates.extend(raw_results)
        except Exception:
            pass

    # Score and classify candidates
    scored_candidates: list[dict[str, Any]] = []
    seen_identifiers: set[str] = {business_name.strip().lower()}

    for cand in candidates:
        cand_key = cand.name.strip().lower()
        if cand_key in seen_identifiers:
            continue
        seen_identifiers.add(cand_key)

        confidence, comp_type, reason = calculate_competitor_relevance(
            target_name=business_name,
            target_category=business_category,
            candidate_name=cand.name,
            candidate_category=cand.category,
        )

        # Filter out unrelated businesses
        if comp_type == "unrelated":
            continue

        scored_candidates.append({
            "business": cand,
            "competitor_type": comp_type,
            "confidence_score": round(confidence, 2),
            "qualification_reason": reason,
        })

    # Sort candidates by relevance: direct before indirect, then confidence desc
    scored_candidates.sort(
        key=lambda x: (1 if x["competitor_type"] == "direct" else 0, x["confidence_score"]),
        reverse=True,
    )
    selected = scored_candidates[:max_competitors]

    # Optionally enrich digital presence of top competitors
    enriched_competitors: list[dict[str, Any]] = []
    for entry in selected:
        cand_biz: Business = entry["business"]
        digital_profile: dict[str, Any] = {
            "has_website": bool(cand_biz.website),
            "website": cand_biz.website,
            "has_phone": bool(cand_biz.phone),
            "has_email": bool(cand_biz.email),
            "rating": cand_biz.rating,
            "review_count": cand_biz.review_count,
            "social_links_count": sum(1 for val in (cand_biz.linkedin_url, cand_biz.twitter_url, cand_biz.facebook_url) if val),
            "website_status": "not_analyzed",
        }

        # Analyze website if available and requested
        if enrich_websites and cand_biz.website:
            try:
                web_res = await analyze_target_website(cand_biz.website, check_broken_links=False)
                digital_profile["website_status"] = web_res.get("status", "error")
                digital_profile["website_available"] = web_res.get("available", False)
                digital_profile["response_time_seconds"] = web_res.get("response_time_seconds")
                digital_profile["has_mobile_viewport"] = web_res.get("metadata", {}).get("has_mobile_viewport", False)
                digital_profile["social_profiles_found"] = sum(
                    len(p) for p in web_res.get("social_profiles", {}).values()
                )
            except Exception as e:
                digital_profile["website_status"] = "error"
                digital_profile["website_error"] = str(e)

        enriched_competitors.append({
            "id": cand_biz.id,
            "name": cand_biz.name,
            "category": cand_biz.category,
            "address": cand_biz.address,
            "city": cand_biz.city,
            "state": cand_biz.state,
            "country": cand_biz.country,
            "competitor_type": entry["competitor_type"],
            "confidence_score": entry["confidence_score"],
            "qualification_reason": entry["qualification_reason"],
            "digital_presence": digital_profile,
            "source": cand_biz.source,
        })

    return {
        "target_business": {
            "name": business_name,
            "category": business_category,
            "location": location_str,
            "website": website,
        },
        "total_competitors_found": len(enriched_competitors),
        "competitors": enriched_competitors,
        "provider": source_provider,
        "note": (
            "Competitors identified via industry taxonomy and geographical relevance. "
            "ODbL attribution applies for OpenStreetMap data."
        ),
    }
