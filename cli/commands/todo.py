import click

from cli.commands._util import client, engagement_option
from cli.output import emit, success

LIST_COLUMNS = [
    ("ID", "id"),
    ("Title", "title"),
    ("Status", "status_label"),
    ("Assignee", "assignee.username"),
]


def register(cli):
    cli.add_command(todo_group)


@click.group("todo")
def todo_group():
    """Manage an engagement's task checklist."""


@todo_group.command("list")
@engagement_option
@click.pass_context
def list_(ctx, engagement_id):
    """List an engagement's tasks."""
    result = client(ctx).get(f"/engagements/{engagement_id}/todos")
    emit(ctx, result, columns=LIST_COLUMNS, list_key="todos")


@todo_group.command("create")
@engagement_option
@click.option("--title", required=True)
@click.option("--notes")
@click.pass_context
def create(ctx, engagement_id, title, notes):
    """Add a task. New tasks start open and unassigned."""
    result = client(ctx).post(f"/engagements/{engagement_id}/todos", json={"title": title, "notes": notes})
    emit(ctx, result)


@todo_group.command("get")
@engagement_option
@click.argument("todo_id", type=int)
@click.pass_context
def get(ctx, engagement_id, todo_id):
    """Get one task."""
    result = client(ctx).get(f"/engagements/{engagement_id}/todos/{todo_id}")
    emit(ctx, result)


@todo_group.command("claim")
@engagement_option
@click.argument("todo_id", type=int)
@click.pass_context
def claim(ctx, engagement_id, todo_id):
    """Claim a task -- assigns it to you (the API key's owning user)."""
    result = client(ctx).post(f"/engagements/{engagement_id}/todos/{todo_id}/claim")
    emit(ctx, result)


@todo_group.command("handoff")
@engagement_option
@click.argument("todo_id", type=int)
@click.option("--notes", "handoff_notes", help="Notes for whoever picks the task up next.")
@click.pass_context
def handoff(ctx, engagement_id, todo_id, handoff_notes):
    """Hand off a task -- clears its assignee and records handoff notes."""
    result = client(ctx).post(f"/engagements/{engagement_id}/todos/{todo_id}/handoff", json={"handoff_notes": handoff_notes})
    emit(ctx, result)


@todo_group.command("complete")
@engagement_option
@click.argument("todo_id", type=int)
@click.pass_context
def complete(ctx, engagement_id, todo_id):
    """Mark a task done."""
    result = client(ctx).post(f"/engagements/{engagement_id}/todos/{todo_id}/done")
    emit(ctx, result)


@todo_group.command("reopen")
@engagement_option
@click.argument("todo_id", type=int)
@click.pass_context
def reopen(ctx, engagement_id, todo_id):
    """Reopen a completed task."""
    result = client(ctx).post(f"/engagements/{engagement_id}/todos/{todo_id}/reopen")
    emit(ctx, result)


@todo_group.command("delete")
@engagement_option
@click.argument("todo_id", type=int)
@click.pass_context
def delete(ctx, engagement_id, todo_id):
    """Delete a task."""
    client(ctx).delete(f"/engagements/{engagement_id}/todos/{todo_id}")
    success(f"Deleted task {todo_id}.")
