from typing import List, Optional

from mcp_server import client


def register(mcp):
    @mcp.tool()
    def killchain_list(engagement_id: int) -> dict:
        """List an engagement's kill chain entries."""
        return client.get(f"/engagements/{engagement_id}/killchain")

    @mcp.tool()
    def killchain_create(
        engagement_id: int,
        stage: str,
        title: str,
        description: Optional[str] = None,
        host: Optional[str] = None,
        infra_node_id: Optional[int] = None,
        occurred_at: Optional[str] = None,
        occurred_ended_at: Optional[str] = None,
        loot_file_ids: Optional[List[int]] = None,
    ) -> dict:
        """Add a kill chain entry. Valid stage values depend on the
        engagement's kill chain model (see the engagement's kill_chain_model
        field): reconnaissance, weaponization, delivery, exploitation,
        installation, command_and_control, actions_on_objectives for the
        Lockheed Martin Cyber Kill Chain (the default); reconnaissance,
        weaponization, delivery, social_engineering, exploitation,
        persistence, defense_evasion, command_and_control, pivoting,
        discovery, privilege_escalation, execution, credential_access,
        lateral_movement, collection, exfiltration, impact, objectives for
        the Unified Kill Chain. occurred_at/occurred_ended_at are ISO 8601
        datetimes; occurred_ended_at must not be before occurred_at."""
        payload = {
            "stage": stage,
            "title": title,
            "description": description,
            "host": host,
            "infra_node_id": infra_node_id,
            "occurred_at": occurred_at,
            "occurred_ended_at": occurred_ended_at,
        }
        if loot_file_ids is not None:
            payload["loot_file_ids"] = loot_file_ids
        return client.post(f"/engagements/{engagement_id}/killchain", json=payload)

    @mcp.tool()
    def killchain_get(engagement_id: int, entry_id: int) -> dict:
        """Get one kill chain entry."""
        return client.get(f"/engagements/{engagement_id}/killchain/{entry_id}")

    @mcp.tool()
    def killchain_update(
        engagement_id: int,
        entry_id: int,
        stage: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        host: Optional[str] = None,
        infra_node_id: Optional[int] = None,
        occurred_at: Optional[str] = None,
        occurred_ended_at: Optional[str] = None,
        loot_file_ids: Optional[List[int]] = None,
    ) -> dict:
        """Update a kill chain entry. Only the fields you pass are changed.
        Passing loot_file_ids replaces the entire linked-evidence set."""
        payload = {
            k: v
            for k, v in {
                "stage": stage,
                "title": title,
                "description": description,
                "host": host,
                "infra_node_id": infra_node_id,
                "occurred_at": occurred_at,
                "occurred_ended_at": occurred_ended_at,
            }.items()
            if v is not None
        }
        if loot_file_ids is not None:
            payload["loot_file_ids"] = loot_file_ids
        return client.patch(f"/engagements/{engagement_id}/killchain/{entry_id}", json=payload)

    @mcp.tool()
    def killchain_delete(engagement_id: int, entry_id: int) -> dict:
        """Delete a kill chain entry."""
        return client.delete(f"/engagements/{engagement_id}/killchain/{entry_id}")

    @mcp.tool()
    def killchain_report_html(engagement_id: int) -> str:
        """Render the engagement's kill-chain/IOC client report as an HTML document."""
        return client.get_text(f"/engagements/{engagement_id}/killchain/report")

    @mcp.tool()
    def killchain_report_pdf(engagement_id: int, save_path: str) -> dict:
        """Render the engagement's kill-chain/IOC client report as a PDF, saved
        to a local path on the machine running this MCP server."""
        return client.download(f"/engagements/{engagement_id}/killchain/report.pdf", save_path)
