import click

from cli.commands._util import client, engagement_option, payload
from cli.output import emit, success

NODE_COLUMNS = [
    ("ID", "id"),
    ("Type", "node_type"),
    ("Name", "name"),
    ("Role", "role"),
    ("Status", "status"),
]

EDGE_COLUMNS = [
    ("ID", "id"),
    ("Source", "source_node.name"),
    ("Target", "target_node.name"),
    ("Label", "label"),
]

NODE_TYPES = [
    "hostname",
    "ip_address",
    "domain",
    "region",
    "cloud_provider",
    "file_share",
    "cloud_storage",
    "database",
    "wiki",
    "source_control",
    "ticketing",
    "collaboration",
    "backup_system",
]
ROLES = ["target", "victim"]
STATUSES = ["healthy", "isolated", "dead"]


def register(cli):
    cli.add_command(target_group)


@click.group("target")
def target_group():
    """Manage target/victim nodes -- the systems being attacked, not
    attacker-owned infrastructure (see the `infra` command for that).
    """


@target_group.group("node")
def node_group():
    """Manage target/victim nodes."""


@node_group.command("list")
@engagement_option
@click.pass_context
def node_list(ctx, engagement_id):
    """List target/victim nodes."""
    result = client(ctx).get(f"/engagements/{engagement_id}/targets/nodes")
    emit(ctx, result, columns=NODE_COLUMNS, list_key="nodes")


@node_group.command("create")
@engagement_option
@click.option("--type", "node_type", required=True, type=click.Choice(NODE_TYPES))
@click.option("--name", required=True)
@click.option("--role", required=True, type=click.Choice(ROLES))
@click.option("--status", type=click.Choice(STATUSES))
@click.option("--provider")
@click.option("--region")
@click.option("--notes")
@click.pass_context
def node_create(ctx, engagement_id, node_type, name, role, status, provider, region, notes):
    """Add a target/victim node."""
    body = payload(node_type=node_type, name=name, role=role, status=status, provider=provider, region=region, notes=notes)
    result = client(ctx).post(f"/engagements/{engagement_id}/targets/nodes", json=body)
    emit(ctx, result)


@node_group.command("get")
@engagement_option
@click.argument("node_id", type=int)
@click.pass_context
def node_get(ctx, engagement_id, node_id):
    """Get one target/victim node."""
    result = client(ctx).get(f"/engagements/{engagement_id}/targets/nodes/{node_id}")
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
    """Update a target/victim node. Only the options you pass are changed."""
    body = payload(node_type=node_type, name=name, role=role, status=status, provider=provider, region=region, notes=notes)
    result = client(ctx).patch(f"/engagements/{engagement_id}/targets/nodes/{node_id}", json=body)
    emit(ctx, result)


@node_group.command("delete")
@engagement_option
@click.argument("node_id", type=int)
@click.pass_context
def node_delete(ctx, engagement_id, node_id):
    """Delete a target/victim node."""
    client(ctx).delete(f"/engagements/{engagement_id}/targets/nodes/{node_id}")
    success(f"Deleted target node {node_id}.")


@target_group.group("edge")
def edge_group():
    """Manage network paths between target/victim nodes."""


@edge_group.command("list")
@engagement_option
@click.pass_context
def edge_list(ctx, engagement_id):
    """List network paths between target/victim nodes."""
    result = client(ctx).get(f"/engagements/{engagement_id}/targets/edges")
    emit(ctx, result, columns=EDGE_COLUMNS, list_key="edges")


@edge_group.command("create")
@engagement_option
@click.option("--source", "source_node_id", type=int, required=True)
@click.option("--target", "target_node_id", type=int, required=True)
@click.option("--label")
@click.option("--notes")
@click.pass_context
def edge_create(ctx, engagement_id, source_node_id, target_node_id, label, notes):
    """Add a network path between two target/victim nodes."""
    body = {"source_node_id": source_node_id, "target_node_id": target_node_id, "label": label, "notes": notes}
    result = client(ctx).post(f"/engagements/{engagement_id}/targets/edges", json=body)
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
    result = client(ctx).patch(f"/engagements/{engagement_id}/targets/edges/{edge_id}", json=body)
    emit(ctx, result)


@edge_group.command("delete")
@engagement_option
@click.argument("edge_id", type=int)
@click.pass_context
def edge_delete(ctx, engagement_id, edge_id):
    """Delete a network path."""
    client(ctx).delete(f"/engagements/{engagement_id}/targets/edges/{edge_id}")
    success(f"Deleted edge {edge_id}.")
