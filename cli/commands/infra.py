import click

from cli.commands._util import client, engagement_option, payload
from cli.output import emit, success

NODE_COLUMNS = [
    ("ID", "id"),
    ("Type", "node_type"),
    ("Name", "name"),
    ("Role", "role"),
    ("Status", "status"),
    ("Provider", "provider"),
]

EDGE_COLUMNS = [
    ("ID", "id"),
    ("Source", "source_node.name"),
    ("Target", "target_node.name"),
    ("Label", "label"),
]

NODE_TYPES = ["hostname", "ip_address", "domain", "region", "cloud_provider"]
ROLES = ["redirector", "team_server", "pivot", "proxy", "C2", "OSINT", "other"]
STATUSES = ["healthy", "burned"]


def register(cli):
    cli.add_command(infra_group)


@click.group("infra")
def infra_group():
    """Manage attacker-owned infrastructure (redirectors, team servers, C2,
    proxies, etc.) -- not targets/victims, see the `target` command for that.
    """


@infra_group.group("node")
def node_group():
    """Manage infrastructure nodes."""


@node_group.command("list")
@engagement_option
@click.pass_context
def node_list(ctx, engagement_id):
    """List attacker-owned infrastructure nodes."""
    result = client(ctx).get(f"/engagements/{engagement_id}/infrastructure/nodes")
    emit(ctx, result, columns=NODE_COLUMNS, list_key="nodes")


@node_group.command("create")
@engagement_option
@click.option("--type", "node_type", required=True, type=click.Choice(NODE_TYPES))
@click.option("--name", required=True)
@click.option("--role", type=click.Choice(ROLES))
@click.option("--status", type=click.Choice(STATUSES))
@click.option("--provider")
@click.option("--region")
@click.option("--notes")
@click.pass_context
def node_create(ctx, engagement_id, node_type, name, role, status, provider, region, notes):
    """Add an infrastructure node."""
    body = payload(node_type=node_type, name=name, role=role, status=status, provider=provider, region=region, notes=notes)
    result = client(ctx).post(f"/engagements/{engagement_id}/infrastructure/nodes", json=body)
    emit(ctx, result)


@node_group.command("get")
@engagement_option
@click.argument("node_id", type=int)
@click.pass_context
def node_get(ctx, engagement_id, node_id):
    """Get one infrastructure node, including its services."""
    result = client(ctx).get(f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}")
    emit(ctx, result)


@node_group.command("update")
@engagement_option
@click.argument("node_id", type=int)
@click.option("--type", "node_type", type=click.Choice(NODE_TYPES))
@click.option("--name")
@click.option("--role", type=click.Choice(ROLES))
@click.option("--status", type=click.Choice(STATUSES))
@click.option("--provider")
@click.option("--region")
@click.option("--notes")
@click.pass_context
def node_update(ctx, engagement_id, node_id, node_type, name, role, status, provider, region, notes):
    """Update an infrastructure node. Only the options you pass are changed."""
    body = payload(node_type=node_type, name=name, role=role, status=status, provider=provider, region=region, notes=notes)
    result = client(ctx).patch(f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}", json=body)
    emit(ctx, result)


@node_group.command("delete")
@engagement_option
@click.argument("node_id", type=int)
@click.pass_context
def node_delete(ctx, engagement_id, node_id):
    """Delete an infrastructure node (and its services)."""
    client(ctx).delete(f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}")
    success(f"Deleted infrastructure node {node_id}.")


@infra_group.group("service")
def service_group():
    """Manage services attached to infrastructure nodes."""


@service_group.command("add")
@engagement_option
@click.argument("node_id", type=int)
@click.option("--name", required=True, help="e.g. https")
@click.option("--port", type=int)
@click.pass_context
def service_add(ctx, engagement_id, node_id, name, port):
    """Add a service to an infrastructure node."""
    result = client(ctx).post(
        f"/engagements/{engagement_id}/infrastructure/nodes/{node_id}/services", json={"name": name, "port": port}
    )
    emit(ctx, result)


@service_group.command("delete")
@engagement_option
@click.argument("service_id", type=int)
@click.pass_context
def service_delete(ctx, engagement_id, service_id):
    """Remove a service from an infrastructure node."""
    client(ctx).delete(f"/engagements/{engagement_id}/infrastructure/services/{service_id}")
    success(f"Deleted service {service_id}.")


@infra_group.group("edge")
def edge_group():
    """Manage network paths between infrastructure nodes."""


@edge_group.command("list")
@engagement_option
@click.pass_context
def edge_list(ctx, engagement_id):
    """List network paths between infrastructure nodes."""
    result = client(ctx).get(f"/engagements/{engagement_id}/infrastructure/edges")
    emit(ctx, result, columns=EDGE_COLUMNS, list_key="edges")


@edge_group.command("create")
@engagement_option
@click.option("--source", "source_node_id", type=int, required=True)
@click.option("--target", "target_node_id", type=int, required=True)
@click.option("--label")
@click.option("--notes")
@click.pass_context
def edge_create(ctx, engagement_id, source_node_id, target_node_id, label, notes):
    """Add a network path between two infrastructure nodes (e.g. victim -> redirector -> team server)."""
    body = {"source_node_id": source_node_id, "target_node_id": target_node_id, "label": label, "notes": notes}
    result = client(ctx).post(f"/engagements/{engagement_id}/infrastructure/edges", json=body)
    emit(ctx, result)


@edge_group.command("update")
@engagement_option
@click.argument("edge_id", type=int)
@click.option("--source", "source_node_id", type=int)
@click.option("--target", "target_node_id", type=int)
@click.option("--label")
@click.option("--notes")
@click.pass_context
def edge_update(ctx, engagement_id, edge_id, source_node_id, target_node_id, label, notes):
    """Update a network path. Only the options you pass are changed."""
    body = payload(source_node_id=source_node_id, target_node_id=target_node_id, label=label, notes=notes)
    result = client(ctx).patch(f"/engagements/{engagement_id}/infrastructure/edges/{edge_id}", json=body)
    emit(ctx, result)


@edge_group.command("delete")
@engagement_option
@click.argument("edge_id", type=int)
@click.pass_context
def edge_delete(ctx, engagement_id, edge_id):
    """Delete a network path."""
    client(ctx).delete(f"/engagements/{engagement_id}/infrastructure/edges/{edge_id}")
    success(f"Deleted edge {edge_id}.")


@infra_group.command("graph")
@engagement_option
@click.pass_context
def graph(ctx, engagement_id):
    """Get the full network graph (all nodes, edges, and kill chain entries ordered by time)."""
    result = client(ctx).get(f"/engagements/{engagement_id}/infrastructure/graph.json")
    emit(ctx, result)
