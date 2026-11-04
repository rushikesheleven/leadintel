"""
LeadIntel MCP Server
====================
Free, open-source MCP server for B2B lead generation and business intelligence.

Data sources:
  - OpenStreetMap / Overpass API (free, ODbL licence)
  - Demo data (always available, no network required)

Entry point — run with:
    uv run python -m leadintel.server
or for interactive MCP Inspector:
    uv run mcp dev src/leadintel/server.py
"""

from __future__ import annotations

import logging

from mcp.server.mcpserver import MCPServer

from .config import settings
from .tools import register_all

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("leadintel")

# ── MCP Server ────────────────────────────────────────────────────────────────
mcp = MCPServer(
    name="leadintel",
    version="0.1.0",
    instructions=(
        "LeadIntel is a free, open-source MCP server for B2B lead generation "
        "and business intelligence. It uses OpenStreetMap (free, no API key "
        "required) for live business discovery. Use search_businesses to find "
        "businesses in any city, export_leads to save results, and the "
        "upcoming tools (analyze_website, score_lead, etc.) for enrichment. "
        "When source is 'openstreetmap', you MUST display the attribution: "
        "'Data © OpenStreetMap contributors, ODbL 1.0'."
    ),
)

# Register all tools
register_all(mcp)

logger.info("LeadIntel MCP server initialised. Config: %s", settings.safe_dict())

# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run()
