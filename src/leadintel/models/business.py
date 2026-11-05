"""Business data models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer

WebsiteStatus = Literal[
    "website_verified",
    "website_not_found_after_research",
    "website_unverified",
    "website_broken",
    "website_not_checked",
]


class Business(BaseModel):
    """Represents a single business entity."""

    # Identity
    id: str = Field(description="Stable unique identifier (e.g. 'osm_node_12345' or slug)")
    name: str = Field(description="Business name")
    category: Optional[str] = Field(default=None, description="Primary industry / category")

    # Location
    address: Optional[str] = Field(default=None, description="Full formatted address")
    city: Optional[str] = Field(default=None)
    state: Optional[str] = Field(default=None)
    country: Optional[str] = Field(default=None)
    postal_code: Optional[str] = Field(default=None)
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    distance_meters: Optional[float] = Field(
        default=None,
        ge=0,
        description="Calculated distance in metres from the search center coordinates",
    )
    distance_km: Optional[float] = Field(
        default=None,
        ge=0,
        description="Calculated distance in kilometres from search center",
    )

    # Contact & Digital Presence
    phone: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    website: Optional[str] = Field(default=None)
    website_status: WebsiteStatus = Field(
        default="website_not_checked",
        description=(
            "Verification status of the business website. One of: "
            "'website_verified', 'website_not_found_after_research', "
            "'website_unverified', 'website_broken', 'website_not_checked'."
        ),
    )
    website_opportunity_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Deterministic 0–100 score prioritizing web dev opportunity for agencies",
    )
    website_opportunity_explanation: Optional[str] = Field(
        default=None,
        description="Evidence-based explanation of the website opportunity score",
    )
    detected_cms: Optional[str] = Field(
        default=None,
        description="Detected CMS like WordPress, Shopify, Wix",
    )
    has_contact_route: Optional[bool] = Field(
        default=None,
        description="True if a contact page or mailto link was found",
    )

    # Social
    linkedin_url: Optional[str] = Field(default=None)
    twitter_url: Optional[str] = Field(default=None)
    facebook_url: Optional[str] = Field(default=None)

    # Metrics
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    review_count: Optional[int] = Field(default=None, ge=0)
    employee_count_estimate: Optional[str] = Field(
        default=None, description="Rough headcount range, e.g. '10–50'"
    )

    # Provenance — every record must carry this for compliance
    source: str = Field(
        default="demo",
        description=(
            "Data source identifier. "
            "'openstreetmap' → ODbL licence applies; "
            "'demo' → synthetic data."
        ),
    )
    attribution: Optional[str] = Field(
        default=None,
        description=(
            "Required attribution string when source is 'openstreetmap'. "
            "Must be displayed wherever data is shown or exported."
        ),
    )
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    is_ai_generated: bool = Field(
        default=False,
        description="True when any field value was produced by an AI model",
    )
    data_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence indicator for data completeness and verification",
    )
    osm_tags: Optional[dict[str, str]] = Field(
        default=None,
        description="Preserved raw OpenStreetMap tags for transparency and auditability",
    )
    ranking_explanation: Optional[str] = Field(
        default=None,
        description="Human-readable explanation of why this business was ranked in this search position",
    )

    model_config = ConfigDict()

    @field_serializer("retrieved_at")
    def serialise_retrieved_at(self, v: datetime) -> str:
        return v.isoformat()

    @property
    def osm_id(self) -> Optional[str]:
        """Return the raw OSM element ID string if this record came from OSM."""
        if self.id.startswith("osm_"):
            return self.id
        return None

    @property
    def requires_attribution(self) -> bool:
        """True when the ODbL attribution string must be displayed."""
        return self.source == "openstreetmap"


class BusinessSearchResult(BaseModel):
    """Wrapper returned by search_businesses."""

    query: str
    location: Optional[str] = None
    category: Optional[str] = None
    search_center: Optional[dict[str, float]] = Field(
        default=None,
        description="Resolved search center coordinates {'latitude': lat, 'longitude': lon}",
    )
    radius_meters: Optional[int] = Field(
        default=None,
        description="Search radius in metres applied around search center",
    )
    sort_by: Optional[str] = Field(
        default=None,
        description="Applied ranking criterion (e.g. 'highest_website_opportunity', 'closest')",
    )
    total_found: int = 0
    businesses: list[Business] = Field(default_factory=list)
    source: str = "demo"
    provider: str = "demo"
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    note: Optional[str] = Field(
        default=None,
        description="Human-readable note about data quality, limits, or caveats",
    )
    attribution: Optional[str] = Field(
        default=None,
        description="Attribution string — required when source is 'openstreetmap'.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error details if the search provider encountered an issue",
    )

    @field_serializer("retrieved_at")
    def serialise_retrieved_at(self, v: datetime) -> str:
        return v.isoformat()


class LeadScore(BaseModel):
    """Lead quality score for a business."""

    business_id: str
    business_name: str
    score: float = Field(ge=0, le=100, description="0–100 lead quality score")
    grade: str = Field(description="A / B / C / D / F")
    factors: dict[str, float] = Field(
        default_factory=dict,
        description="Breakdown of individual scoring dimensions",
    )
    recommendation: str = Field(default="", description="Short actionable text")
    scored_at: datetime = Field(default_factory=datetime.utcnow)
    is_ai_generated: bool = False

    @field_serializer("scored_at")
    def serialise_scored_at(self, v: datetime) -> str:
        return v.isoformat()
