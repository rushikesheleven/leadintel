"""
MCP Tool: get_saved_leads

Retrieves previously researched and stored business leads from the local SQLite database.
Supports filtering by minimum website opportunity score and configurable record limits.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from mcp.server.mcpserver import MCPServer

from ..storage.db import get_all_businesses

logger = logging.getLogger(__name__)


def register(mcp: MCPServer) -> None:
    """Register get_saved_leads tool on the MCP server."""

    @mcp.tool()
    async def get_saved_leads(
        min_opportunity_score: Optional[float] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Retrieve previously researched businesses saved in the local LeadIntel SQLite database.

        Allows filtering leads by minimum website opportunity score, making it easy
        to fetch high-priority web development or digital agency prospects.

        Args:
            min_opportunity_score: Optional minimum website opportunity score (0–100) to filter by.
            limit: Maximum number of businesses to return (default: 50, max: 200).

        Returns:
            Dict containing retrieved leads, count, and applied query filters.
        """
        clamped_limit = max(1, min(limit, 200))
        try:
            businesses = get_all_businesses(min_score=min_opportunity_score, limit=clamped_limit)
            return {
                "total_retrieved": len(businesses),
                "min_opportunity_score": min_opportunity_score,
                "limit": clamped_limit,
                "businesses": [b.model_dump(mode="json") for b in businesses],
            }
        except Exception as exc:
            logger.warning("Failed to retrieve saved leads from database: %s", exc)
            return {
                "error": "Failed to retrieve saved leads from local database.",
                "message": str(exc),
                "total_retrieved": 0,
                "businesses": [],
            }

