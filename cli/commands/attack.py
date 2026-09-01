import click

from cli.commands._util import client, engagement_option
from cli.output import emit, success

TACTIC_COLUMNS = [
    ("Tactic", "attack_id"),
    ("Name", "name"),
    ("Techniques", lambda row: len(row.get("techniques", []))),
]


def register(cli):
    cli.add_command(attack_group)


@click.group("attack")
def attack_group():
    """MITRE ATT&CK technique lookup and mapping."""


@attack_group.command("tactics")
@click.pass_context
def tactics(ctx):
    """List the ATT&CK Enterprise matrix (tactics with their top-level techniques)."""
    result = client(ctx).get("/attack/tactics")
    emit(ctx, result, columns=TACTIC_COLUMNS, list_key="tactics")


@attack_group.command("technique")
@click.argument("attack_id")
@click.pass_context
def technique(ctx, attack_id):
    """Get one ATT&CK technique by id (e.g. T1566)."""
    result = client(ctx).get(f"/attack/techniques/{attack_id}")
    emit(ctx, result)


@attack_group.command("refresh")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
@click.pass_context
def refresh(ctx, yes):
    """Re-sync the local ATT&CK cache from MITRE's public STIX feed.

    Requires an admin-role API key. Makes a live outbound request to
    MITRE's GitHub and can take a while.
    """
    if not yes:
        click.confirm("This fetches the full ATT&CK matrix from MITRE's GitHub and can take a while. Continue?", abort=True)
    result = client(ctx).post("/attack/refresh")
    emit(ctx, result)


@attack_group.command("map-loot")
@engagement_option
@click.argument("file_id", type=int)
@click.option("--technique", "attack_id", required=True, help="ATT&CK technique id, e.g. T1566.")
@click.option("--notes")
@click.pass_context
def map_loot(ctx, engagement_id, file_id, attack_id, notes):
    """Map an ATT&CK technique to a loot file as evidence of its use."""
    result = client(ctx).post(
        f"/engagements/{engagement_id}/loot/{file_id}/map-technique", json={"attack_id": attack_id, "notes": notes}
    )
    emit(ctx, result)


@attack_group.command("map-killchain")
@engagement_option
@click.argument("entry_id", type=int)
@click.option("--technique", "attack_id", required=True, help="ATT&CK technique id, e.g. T1566.")
@click.option("--notes")
@click.pass_context
def map_killchain(ctx, engagement_id, entry_id, attack_id, notes):
    """Map an ATT&CK technique to a kill chain entry as evidence of its use."""
    result = client(ctx).post(
        f"/engagements/{engagement_id}/killchain/{entry_id}/map-technique", json={"attack_id": attack_id, "notes": notes}
    )
    emit(ctx, result)


@attack_group.command("unmap")
@click.argument("mapping_id", type=int)
@click.pass_context
def unmap(ctx, mapping_id):
    """Remove a technique mapping (from either a loot file or a kill chain entry)."""
    client(ctx).delete(f"/technique-mappings/{mapping_id}")
    success(f"Deleted technique mapping {mapping_id}.")
