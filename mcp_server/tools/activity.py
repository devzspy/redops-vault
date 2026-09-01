from mcp_server import client


def register(mcp):
    @mcp.tool()
    def activity_list(engagement_id: int, limit: int = 50) -> dict:
        """List an engagement's audit-trail activity log, most recent first --
        useful for catching up on what's happened in an engagement."""
        return client.get(f"/engagements/{engagement_id}/activity", params={"limit": limit})
