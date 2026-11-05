"""LeadIntel — open-source MCP server for B2B lead generation."""

from .storage.db import init_db

__version__ = "0.3.0"
__all__ = ["init_db", "__version__"]
