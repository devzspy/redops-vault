import click

from cli.commands._util import client, engagement_option, payload
from cli.output import console, emit, success

LIST_COLUMNS = [
    ("ID", "id"),
    ("Stage", "stage_label"),
    ("Title", "title"),
    ("Host", "host"),
    ("Occurred", "occurred_range_label"),
]

def _loot_ids(ctx, param, value):
    if not value:
        return None
    try:
        return [int(v.strip()) for v in value.split(",") if v.strip()]
    except ValueError as exc:
        raise click.BadParameter("must be a comma-separated list of integers") from exc


def register(cli):
    cli.add_command(killchain_group)


@click.group("killchain")
def killchain_group():
    """Manage kill chain entries."""


@killchain_group.command("list")
@engagement_option
@click.pass_context
def list_(ctx, engagement_id):
    """List an engagement's kill chain entries."""
    result = client(ctx).get(f"/engagements/{engagement_id}/killchain")
    emit(ctx, result, columns=LIST_COLUMNS, list_key="entries")


@killchain_group.command("create")
@engagement_option
@click.option("--stage", required=True, help="Stage slug valid for the engagement's kill chain model (Lockheed Martin or Unified Kill Chain).")
@click.option("--title", required=True)
@click.option("--description")
@click.option("--host")
@click.option("--infra-node-id", type=int)
@click.option("--occurred-at", help="ISO 8601 datetime.")
@click.option("--occurred-ended-at", help="ISO 8601 datetime; must not be before --occurred-at.")
@click.option("--loot-file-ids", callback=_loot_ids, help="Comma-separated loot file IDs as evidence.")
@click.pass_context
def create(ctx, engagement_id, stage, title, description, host, infra_node_id, occurred_at, occurred_ended_at, loot_file_ids):
    """Add a kill chain entry."""
    body = payload(
        stage=stage, title=title, description=description, host=host, infra_node_id=infra_node_id,
        occurred_at=occurred_at, occurred_ended_at=occurred_ended_at,
    )
    if loot_file_ids is not None:
        body["loot_file_ids"] = loot_file_ids
    result = client(ctx).post(f"/engagements/{engagement_id}/killchain", json=body)
    emit(ctx, result)


@killchain_group.command("get")
@engagement_option
@click.argument("entry_id", type=int)
@click.pass_context
def get(ctx, engagement_id, entry_id):
    """Get one kill chain entry."""
    result = client(ctx).get(f"/engagements/{engagement_id}/killchain/{entry_id}")
    emit(ctx, result)


@killchain_group.command("update")
@engagement_option
@click.argument("entry_id", type=int)
@click.option("--stage", help="Stage slug valid for the engagement's kill chain model (Lockheed Martin or Unified Kill Chain).")
@click.option("--title")
@click.option("--description")
@click.option("--host")
@click.option("--infra-node-id", type=int)
@click.option("--occurred-at")
@click.option("--occurred-ended-at")
@click.option("--loot-file-ids", callback=_loot_ids, help="Comma-separated loot file IDs; replaces the whole evidence set.")
@click.pass_context
def update(ctx, engagement_id, entry_id, stage, title, description, host, infra_node_id, occurred_at, occurred_ended_at, loot_file_ids):
    """Update a kill chain entry. Only the options you pass are changed."""
    body = payload(
        stage=stage, title=title, description=description, host=host, infra_node_id=infra_node_id,
        occurred_at=occurred_at, occurred_ended_at=occurred_ended_at,
    )
    if loot_file_ids is not None:
        body["loot_file_ids"] = loot_file_ids
    result = client(ctx).patch(f"/engagements/{engagement_id}/killchain/{entry_id}", json=body)
    emit(ctx, result)


@killchain_group.command("delete")
@engagement_option
@click.argument("entry_id", type=int)
@click.pass_context
def delete(ctx, engagement_id, entry_id):
    """Delete a kill chain entry."""
    client(ctx).delete(f"/engagements/{engagement_id}/killchain/{entry_id}")
    success(f"Deleted kill chain entry {entry_id}.")


@killchain_group.command("report")
@engagement_option
@click.option("--pdf", is_flag=True, help="Render as PDF instead of HTML.")
@click.option("--output", "-o", type=click.Path(dir_okay=False), help="Save to a file instead of printing (required with --pdf).")
@click.pass_context
def report(ctx, engagement_id, pdf, output):
    """Export the engagement's kill-chain/IOC client report."""
    if pdf:
        if not output:
            raise click.UsageError("--output is required with --pdf.")
        result = client(ctx).download(f"/engagements/{engagement_id}/killchain/report.pdf", output)
        emit(ctx, result)
        return

    text = client(ctx).get_text(f"/engagements/{engagement_id}/killchain/report")
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(text)
        success(f"Saved report to {output}.")
    else:
        console.print(text, markup=False, highlight=False)
