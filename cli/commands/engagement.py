import click

from cli.commands._util import client, payload
from cli.output import emit, success

LIST_COLUMNS = [
    ("ID", "id"),
    ("Name", "name"),
    ("Client", "client_name"),
    ("Status", "status_label"),
    ("Archived", "is_archived"),
    ("Start", "start_date"),
    ("End", "end_date"),
]

LINK_COLUMNS = [
    ("ID", "id"),
    ("Type", "link_type_label"),
    ("Label", "label"),
    ("URL", "url"),
]


def register(cli):
    cli.add_command(engagement_group)


@click.group("engagement")
def engagement_group():
    """Manage engagements."""


@engagement_group.command("list")
@click.option("--show-archived", is_flag=True, help="Include archived engagements.")
@click.pass_context
def list_(ctx, show_archived):
    """List engagements."""
    result = client(ctx).get("/engagements", params={"show_archived": "1" if show_archived else "0"})
    emit(ctx, result, columns=LIST_COLUMNS, list_key="engagements")


@engagement_group.command("create")
@click.option("--name", required=True)
@click.option("--client-name", required=True)
@click.option("--description")
@click.option("--start-date", help="ISO 8601 date, YYYY-MM-DD.")
@click.option("--end-date", help="ISO 8601 date, YYYY-MM-DD.")
@click.option(
    "--kill-chain-model",
    type=click.Choice(["lmckc", "ukc"]),
    help="Kill chain model for this engagement's entries: lmckc (Lockheed Martin, default) or ukc (Unified Kill Chain).",
)
@click.pass_context
def create(ctx, name, client_name, description, start_date, end_date, kill_chain_model):
    """Create a new engagement."""
    body = payload(
        name=name,
        client_name=client_name,
        description=description,
        start_date=start_date,
        end_date=end_date,
        kill_chain_model=kill_chain_model,
    )
    result = client(ctx).post("/engagements", json=body)
    emit(ctx, result)


@engagement_group.command("get")
@click.argument("engagement_id", type=int)
@click.pass_context
def get(ctx, engagement_id):
    """Get full detail for one engagement."""
    result = client(ctx).get(f"/engagements/{engagement_id}")
    emit(ctx, result)


@engagement_group.command("update")
@click.argument("engagement_id", type=int)
@click.option("--name")
@click.option("--client-name")
@click.option("--description")
@click.option("--start-date")
@click.option("--end-date")
@click.option(
    "--kill-chain-model",
    type=click.Choice(["lmckc", "ukc"]),
    help="Only changeable while the engagement has zero kill chain entries.",
)
@click.pass_context
def update(ctx, engagement_id, name, client_name, description, start_date, end_date, kill_chain_model):
    """Update an engagement. Only the options you pass are changed."""
    body = payload(
        name=name,
        client_name=client_name,
        description=description,
        start_date=start_date,
        end_date=end_date,
        kill_chain_model=kill_chain_model,
    )
    result = client(ctx).patch(f"/engagements/{engagement_id}", json=body)
    emit(ctx, result)


@engagement_group.command("set-status")
@click.argument("engagement_id", type=int)
@click.argument("status", type=click.Choice(["backlog", "planning", "active", "completed"]))
@click.pass_context
def set_status(ctx, engagement_id, status):
    """Set an engagement's Kanban status."""
    result = client(ctx).post(f"/engagements/{engagement_id}/status", json={"status": status})
    emit(ctx, result)


@engagement_group.command("archive")
@click.argument("engagement_id", type=int)
@click.pass_context
def archive(ctx, engagement_id):
    """Toggle an engagement's archived flag (archives it if active, restores it if archived)."""
    result = client(ctx).post(f"/engagements/{engagement_id}/archive")
    emit(ctx, result)


@engagement_group.group("link")
def link_group():
    """Manage an engagement's reference links."""


@link_group.command("list")
@click.argument("engagement_id", type=int)
@click.pass_context
def link_list(ctx, engagement_id):
    """List an engagement's reference links."""
    result = client(ctx).get(f"/engagements/{engagement_id}/links")
    emit(ctx, result, columns=LINK_COLUMNS, list_key="links")


@link_group.command("add")
@click.argument("engagement_id", type=int)
@click.option("--url", required=True)
@click.option("--type", "link_type", type=click.Choice(["external", "internal"]), default="external")
@click.option("--label")
@click.option("--notes")
@click.pass_context
def link_add(ctx, engagement_id, url, link_type, label, notes):
    """Add a reference link to an engagement."""
    body = payload(url=url, link_type=link_type, label=label, notes=notes)
    result = client(ctx).post(f"/engagements/{engagement_id}/links", json=body)
    emit(ctx, result)


@link_group.command("update")
@click.argument("engagement_id", type=int)
@click.argument("link_id", type=int)
@click.option("--url")
@click.option("--type", "link_type", type=click.Choice(["external", "internal"]))
@click.option("--label")
@click.option("--notes")
@click.pass_context
def link_update(ctx, engagement_id, link_id, url, link_type, label, notes):
    """Update an engagement link. Only the options you pass are changed."""
    body = payload(url=url, link_type=link_type, label=label, notes=notes)
    result = client(ctx).patch(f"/engagements/{engagement_id}/links/{link_id}", json=body)
    emit(ctx, result)


@link_group.command("delete")
@click.argument("engagement_id", type=int)
@click.argument("link_id", type=int)
@click.pass_context
def link_delete(ctx, engagement_id, link_id):
    """Delete an engagement link."""
    client(ctx).delete(f"/engagements/{engagement_id}/links/{link_id}")
    success(f"Deleted link {link_id}.")
