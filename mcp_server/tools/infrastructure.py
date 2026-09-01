from typing import Optional

from mcp_server import client


def register(mcp):
    @mcp.tool()
    def infra_node_list(engagement_id: int) -> dict:
        """List attacker-owned infrastructure nodes for an engagement
        (redirectors, team servers, C2, proxies, etc.) -- not targets/victims,
        those are target_list."""
        return client.get(f"/engagements/{engagement_id}/infrastructure/nodes")

    @mcp.tool()
    def infra_node_create(
        engagement_id: int,
        node_type: str,
        name: str,
        role: Optional[str] = None,
        status: Optional[str] = None,
        provider: Optional[str] = None,
        region: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """Add an attacker-owned infrastructure node. node_type is one of:
        hostname, ip_address, domain, region, cloud_provider. role is one of:
        redirector, team_server, pivot, proxy, C2, OSINT, other. status is
        one of: healthy, burned."""
        return client.post(
            f"/engagements/{engagement_id}/infrastructure/nodes",
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
    def infra_node_get(engagement_id: int, node_id: int) -> dict:
        """Get one attacker-owned infrastructure node, including its services."""
        return client.get(f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}")

    @mcp.tool()
    def infra_node_update(
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
        """Update an attacker-owned infrastructure node. Only the fields you pass are changed."""
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
        return client.patch(f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}", json=payload)

    @mcp.tool()
    def infra_node_delete(engagement_id: int, node_id: int) -> dict:
        """Delete an attacker-owned infrastructure node (and its services)."""
        return client.delete(f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}")

    @mcp.tool()
    def infra_service_create(engagement_id: int, node_id: int, name: str, port: Optional[int] = None) -> dict:
        """Add a service (e.g. 'https', port 443) to an infrastructure node."""
        return client.post(
            f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}/services",
            json={"name": name, "port": port},
        )

    @mcp.tool()
    def infra_service_delete(engagement_id: int, service_id: int) -> dict:
        """Remove a service from an infrastructure node."""
        return client.delete(f"/engagements/{engagement_id}/infrastructure/services/{service_id}")

    @mcp.tool()
    def infra_edge_list(engagement_id: int) -> dict:
        """List network paths (edges) between attacker-owned infrastructure nodes."""
        return client.get(f"/engagements/{engagement_id}/infrastructure/edges")

    @mcp.tool()
    def infra_edge_create(
        engagement_id: int, source_node_id: int, target_node_id: int, label: Optional[str] = None, notes: Optional[str] = None
    ) -> dict:
        """Add a network path between two attacker-owned infrastructure nodes
        (e.g. victim -> redirector -> team server)."""
        return client.post(
            f"/engagements/{engagement_id}/infrastructure/edges",
            json={"source_node_id": source_node_id, "target_node_id": target_node_id, "label": label, "notes": notes},
        )

    @mcp.tool()
    def infra_edge_update(
        engagement_id: int,
        edge_id: int,
        source_node_id: Optional[int] = None,
        target_node_id: Optional[int] = None,
        label: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """Update a network path. Only the fields you pass are changed."""
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
        return client.patch(f"/engagements/{engagement_id}/infrastructure/edges/{edge_id}", json=payload)

    @mcp.tool()
    def infra_edge_delete(engagement_id: int, edge_id: int) -> dict:
        """Delete a network path between infrastructure nodes."""
        return client.delete(f"/engagements/{engagement_id}/infrastructure/edges/{edge_id}")

    @mcp.tool()
    def infra_graph(engagement_id: int) -> dict:
        """Get the full network graph for an engagement (all nodes -- both
        attacker infrastructure and targets/victims -- all edges, and kill
        chain entries ordered by time), as used by the Network Map view."""
        return client.get(f"/engagements/{engagement_id}/infrastructure/graph.json")
