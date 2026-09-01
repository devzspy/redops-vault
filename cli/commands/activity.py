import click

from cli.commands._util import client, engagement_option
from cli.output import emit

LIST_COLUMNS = [
    ("ID", "id"),
    ("Actor", "actor_label"),
    ("Entity", "entity_type"),
    ("Action", "action"),
    ("Summary", "summary"),
    ("When", "created_at"),
]


def register(cli):
    cli.add_command(activity_group)


@click.group("activity")
def activity_group():
    """View an engagement's audit-trail activity log."""


@activity_group.command("list")
@engagement_option
@click.option("--limit", type=int, default=50)
@click.pass_context
def list_(ctx, engagement_id, limit):
    """List an engagement's activity log, most recent first."""
    result = client(ctx).get(f"/engagements/{engagement_id}/activity", params={"limit": limit})
    emit(ctx, result, columns=LIST_COLUMNS, list_key="activity")
