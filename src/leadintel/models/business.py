"""Business data models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer


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

    # Contact
    phone: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    website: Optional[str] = Field(default=None)

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
