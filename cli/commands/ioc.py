import click

from cli.commands._util import client, engagement_option, payload
from cli.output import emit, success

LIST_COLUMNS = [
    ("ID", "id"),
    ("Label", "display_label"),
    ("Host", "host"),
    ("Hash type", "hash_type_label"),
    ("Dropped", "dropped_at"),
]


def register(cli):
    cli.add_command(ioc_group)


@click.group("ioc")
def ioc_group():
    """Manage indicators of compromise."""


@ioc_group.command("list")
@engagement_option
@click.pass_context
def list_(ctx, engagement_id):
    """List an engagement's IOCs."""
    result = client(ctx).get(f"/engagements/{engagement_id}/iocs")
    emit(ctx, result, columns=LIST_COLUMNS, list_key="iocs")


@ioc_group.command("create")
@engagement_option
@click.option("--host")
@click.option("--location")
@click.option("--hash-type", type=click.Choice(["md5", "sha256"]))
@click.option("--hash-value")
@click.option("--dropped-at", help="ISO 8601 datetime.")
@click.option("--notes")
@click.pass_context
def create(ctx, engagement_id, host, location, hash_type, hash_value, dropped_at, notes):
    """Record an IOC."""
    body = payload(host=host, location=location, hash_type=hash_type, hash_value=hash_value, dropped_at=dropped_at, notes=notes)
    result = client(ctx).post(f"/engagements/{engagement_id}/iocs", json=body)
    emit(ctx, result)


@ioc_group.command("get")
@engagement_option
@click.argument("ioc_id", type=int)
@click.pass_context
def get(ctx, engagement_id, ioc_id):
    """Get one IOC."""
    result = client(ctx).get(f"/engagements/{engagement_id}/iocs/{ioc_id}")
    emit(ctx, result)


@ioc_group.command("update")
@engagement_option
@click.argument("ioc_id", type=int)
@click.option("--host")
@click.option("--location")
@click.option("--hash-type", type=click.Choice(["md5", "sha256"]))
@click.option("--hash-value")
@click.option("--dropped-at")
@click.option("--notes")
@click.pass_context
def update(ctx, engagement_id, ioc_id, host, location, hash_type, hash_value, dropped_at, notes):
    """Update an IOC. Only the options you pass are changed."""
    body = payload(host=host, location=location, hash_type=hash_type, hash_value=hash_value, dropped_at=dropped_at, notes=notes)
    result = client(ctx).patch(f"/engagements/{engagement_id}/iocs/{ioc_id}", json=body)
    emit(ctx, result)


@ioc_group.command("delete")
@engagement_option
@click.argument("ioc_id", type=int)
@click.pass_context
def delete(ctx, engagement_id, ioc_id):
    """Delete an IOC."""
    client(ctx).delete(f"/engagements/{engagement_id}/iocs/{ioc_id}")
    success(f"Deleted IOC {ioc_id}.")
