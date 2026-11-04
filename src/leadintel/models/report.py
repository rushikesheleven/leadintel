"""Business report model."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .business import Business, LeadScore


class BusinessReport(BaseModel):
    """Structured intelligence report for a single business."""

    business: Business
    lead_score: Optional[LeadScore] = None
    summary: str = Field(default="", description="Executive summary")
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list, description="Competitor names")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    is_ai_generated: bool = False
    disclaimer: str = Field(
        default=(
            "This report was generated from publicly available data. "
            "Verify all facts independently before making business decisions."
        )
    )
