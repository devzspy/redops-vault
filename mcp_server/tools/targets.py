from typing import Optional

from mcp_server import client


def register(mcp):
    @mcp.tool()
    def target_list(engagement_id: int) -> dict:
        """List target/victim nodes for an engagement (the systems being
        attacked, not attacker-owned infrastructure -- see infra_node_list
        for that)."""
        return client.get(f"/engagements/{engagement_id}/targets/nodes")

    @mcp.tool()
    def target_create(
        engagement_id: int,
        node_type: str,
        name: str,
        role: str,
        status: Optional[str] = None,
        provider: Optional[str] = None,
        region: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """Add a target/victim node. node_type is one of: hostname, ip_address,
        domain, region, cloud_provider, file_share, cloud_storage, database,
        wiki, source_control, ticketing, collaboration, backup_system. role
        is 'target' or 'victim'. status is one of: healthy, isolated, dead."""
        return client.post(
            f"/engagements/{engagement_id}/targets/nodes",
            json={
                "node_type": node_type,
                "name": name,
                "role": role,
                "status": status,
                "provider": provider,
                "region": region,
                "notes": notes,
            },
        )

    @mcp.tool()
    def target_get(engagement_id: int, node_id: int) -> dict:
        """Get one target/victim node."""
        return client.get(f"/engagements/{engagement_id}/targets/nodes/{node_id}")

    @mcp.tool()
    def target_detail_get(engagement_id: int, node_id: int) -> dict:
        """Get the full 'one stop shop' view of a target/victim node: the
        node itself, its network-pathing edges, and every kill chain entry,
        credential, loot file, IOC, and finding correlated to it, plus that
        same set merged into one reverse-chronological timeline. Credentials
        and loot are matched to this host by exact (case-insensitive) name
        -- entries logged under a different hostname/IP for the same system
        won't appear. Credential secrets are omitted; use credential_get
        with reveal=True for those."""
        return client.get(f"/engagements/{engagement_id}/targets/nodes/{node_id}/detail")

    @mcp.tool()
    def target_update(
        engagement_id: int,
        node_id: int,
        node_type: Optional[str] = None,
        name: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
        provider: Optional[str] = None,
        region: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """Update a target/victim node. Only the fields you pass are changed."""
        payload = {
            k: v
            for k, v in {
                "node_type": node_type,
                "name": name,
                "role": role,
                "status": status,
                "provider": provider,
                "region": region,
                "notes": notes,
            }.items()
            if v is not None
        }
        return client.patch(f"/engagements/{engagement_id}/targets/nodes/{node_id}", json=payload)

    @mcp.tool()
    def target_delete(engagement_id: int, node_id: int) -> dict:
        """Delete a target/victim node."""
        return client.delete(f"/engagements/{engagement_id}/targets/nodes/{node_id}")

    @mcp.tool()
    def target_edge_list(engagement_id: int) -> dict:
        """List network paths (edges) between target/victim nodes."""
        return client.get(f"/engagements/{engagement_id}/targets/edges")

    @mcp.tool()
    def target_edge_create(
        engagement_id: int, source_node_id: int, target_node_id: int, label: Optional[str] = None, notes: Optional[str] = None
    ) -> dict:
        """Add a network path between two target/victim nodes."""
        return client.post(
            f"/engagements/{engagement_id}/targets/edges",
            json={"source_node_id": source_node_id, "target_node_id": target_node_id, "label": label, "notes": notes},
        )

    @mcp.tool()
    def target_edge_update(
        engagement_id: int,
        edge_id: int,
        source_node_id: Optional[int] = None,
        target_node_id: Optional[int] = None,
        label: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """Update a network path between target/victim nodes. Only the fields you pass are changed."""
        payload = {
            k: v
            for k, v in {
                "source_node_id": source_node_id,
                "target_node_id": target_node_id,
                "label": label,
                "notes": notes,
            }.items()
            if v is not None
        }
        return client.patch(f"/engagements/{engagement_id}/targets/edges/{edge_id}", json=payload)

    @mcp.tool()
    def target_edge_delete(engagement_id: int, edge_id: int) -> dict:
        """Delete a network path between target/victim nodes."""
        return client.delete(f"/engagements/{engagement_id}/targets/edges/{edge_id}")
