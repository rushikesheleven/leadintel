"""MCP tools package — registers all tools on the shared MCPServer instance."""

from mcp.server.mcpserver import MCPServer

from . import (
    analyze_website,
    check_seo,
    compare_businesses,
    export_leads,
    find_business_website,
    find_competitors,
    find_social_profiles,
    generate_business_insights,
    generate_business_report,
    generate_outreach,
    get_business_details,
    get_saved_leads,
    score_lead,
    search_businesses,
)


def register_all(mcp: MCPServer) -> None:
    """Register every tool on the provided MCP server."""
    search_businesses.register(mcp)
    get_business_details.register(mcp)
    get_saved_leads.register(mcp)
    find_business_website.register(mcp)
    analyze_website.register(mcp)
    check_seo.register(mcp)
    find_social_profiles.register(mcp)
    find_competitors.register(mcp)
    compare_businesses.register(mcp)
    score_lead.register(mcp)
    generate_business_insights.register(mcp)
    generate_outreach.register(mcp)
    generate_business_report.register(mcp)
    export_leads.register(mcp)
