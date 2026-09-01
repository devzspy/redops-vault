from typing import Optional

from mcp_server import client


def register(mcp):
    @mcp.tool()
    def engagement_list(show_archived: bool = False) -> dict:
        """List engagements. Archived engagements are excluded unless show_archived is true."""
        return client.get("/engagements", params={"show_archived": "1" if show_archived else "0"})

    @mcp.tool()
    def engagement_create(
        name: str,
        client_name: str,
        description: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        kill_chain_model: Optional[str] = None,
    ) -> dict:
        """Create a new engagement. Dates are ISO 8601 (YYYY-MM-DD).
        kill_chain_model is 'lmckc' (Lockheed Martin Cyber Kill Chain, the
        default) or 'ukc' (Unified Kill Chain); it determines which kill
        chain stage values are valid for this engagement's entries."""
        return client.post(
            "/engagements",
            json={
                "name": name,
                "client_name": client_name,
                "description": description,
                "start_date": start_date,
                "end_date": end_date,
                "kill_chain_model": kill_chain_model,
            },
        )

    @mcp.tool()
    def engagement_get(engagement_id: int) -> dict:
        """Get full detail for one engagement, including its threat model, links,
        assignments, and counts of loot/findings/credentials/etc. Use the
        dedicated list tools (finding_list, loot_list, ...) to fetch those
        collections themselves."""
        return client.get(f"/engagements/{engagement_id}")

    @mcp.tool()
    def engagement_update(
        engagement_id: int,
        name: Optional[str] = None,
        client_name: Optional[str] = None,
        description: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        kill_chain_model: Optional[str] = None,
    ) -> dict:
        """Update an engagement's fields. Only the fields you pass are changed.
        kill_chain_model ('lmckc' or 'ukc') can only be changed while the
        engagement has zero kill chain entries; the API rejects the change
        otherwise."""
        payload = {
            k: v
            for k, v in {
                "name": name,
                "client_name": client_name,
                "description": description,
                "start_date": start_date,
                "end_date": end_date,
                "kill_chain_model": kill_chain_model,
            }.items()
            if v is not None
        }
        return client.patch(f"/engagements/{engagement_id}", json=payload)

    @mcp.tool()
    def engagement_set_status(engagement_id: int, status: str) -> dict:
        """Set an engagement's status. One of: backlog, planning, active, completed."""
        return client.post(f"/engagements/{engagement_id}/status", json={"status": status})

    @mcp.tool()
    def engagement_toggle_archive(engagement_id: int) -> dict:
        """Toggle an engagement's archived flag (archives it if active, restores it if archived)."""
        return client.post(f"/engagements/{engagement_id}/archive")

    @mcp.tool()
    def engagement_link_list(engagement_id: int) -> dict:
        """List an engagement's reference links (external docs, internal wiki pages, etc.)."""
        return client.get(f"/engagements/{engagement_id}/links")

    @mcp.tool()
    def engagement_link_create(
        engagement_id: int,
        url: str,
        link_type: str = "external",
        label: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """Add a reference link to an engagement. link_type is 'external' or 'internal'."""
        return client.post(
            f"/engagements/{engagement_id}/links",
            json={"url": url, "link_type": link_type, "label": label, "notes": notes},
        )

    @mcp.tool()
    def engagement_link_update(
        engagement_id: int,
        link_id: int,
        url: Optional[str] = None,
        link_type: Optional[str] = None,
        label: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """Update an engagement link. Only the fields you pass are changed."""
        payload = {
            k: v
            for k, v in {"url": url, "link_type": link_type, "label": label, "notes": notes}.items()
            if v is not None
        }
        return client.patch(f"/engagements/{engagement_id}/links/{link_id}", json=payload)

    @mcp.tool()
    def engagement_link_delete(engagement_id: int, link_id: int) -> dict:
        """Delete an engagement link."""
        return client.delete(f"/engagements/{engagement_id}/links/{link_id}")
