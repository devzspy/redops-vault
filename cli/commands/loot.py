import click

from cli.commands._util import client, engagement_option, payload
from cli.output import emit, success

LIST_COLUMNS = [
    ("ID", "id"),
    ("Filename", "original_filename"),
    ("Category", "category"),
    ("Size", "file_size_bytes"),
    ("Host", "associated_host"),
    ("Uploaded", "uploaded_at"),
]

CATEGORIES = ["document", "screenshot", "pcap", "key_cert", "note", "other"]


def register(cli):
    cli.add_command(loot_group)


@click.group("loot")
def loot_group():
    """Manage loot files."""


@loot_group.command("list")
@engagement_option
@click.option("--page", type=int, default=1)
@click.option("--per-page", type=int, default=20)
@click.pass_context
def list_(ctx, engagement_id, page, per_page):
    """List an engagement's loot file metadata (paginated)."""
    result = client(ctx).get(f"/engagements/{engagement_id}/loot", params={"page": page, "per_page": per_page})
    emit(ctx, result, columns=LIST_COLUMNS, list_key="files")


@loot_group.command("upload")
@engagement_option
@click.argument("file_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--category", required=True, type=click.Choice(CATEGORIES))
@click.option("--description")
@click.option("--tags", help="Comma-separated tags.")
@click.option("--associated-host", help="Hostname/IP this file relates to.")
@click.pass_context
def upload(ctx, engagement_id, file_path, category, description, tags, associated_host):
    """Upload a local file as loot, encrypted at rest on the server."""
    result = client(ctx).upload(
        f"/engagements/{engagement_id}/loot",
        file_path,
        {"category": category, "description": description, "tags": tags, "associated_host": associated_host},
    )
    emit(ctx, result)


@loot_group.command("get")
@engagement_option
@click.argument("file_id", type=int)
@click.pass_context
def get(ctx, engagement_id, file_id):
    """Get metadata for one loot file."""
    result = client(ctx).get(f"/engagements/{engagement_id}/loot/{file_id}")
    emit(ctx, result)


@loot_group.command("download")
@engagement_option
@click.argument("file_id", type=int)
@click.argument("save_path", type=click.Path(dir_okay=False))
@click.pass_context
def download(ctx, engagement_id, file_id, save_path):
    """Download and decrypt a loot file to a local path."""
    result = client(ctx).download(f"/engagements/{engagement_id}/loot/{file_id}/download", save_path)
    emit(ctx, result)


@loot_group.command("update")
@engagement_option
@click.argument("file_id", type=int)
@click.option("--category", type=click.Choice(CATEGORIES))
@click.option("--description")
@click.option("--tags")
@click.option("--associated-host")
@click.pass_context
def update(ctx, engagement_id, file_id, category, description, tags, associated_host):
    """Update a loot file's metadata. Contents can't be replaced -- delete and re-upload instead."""
    body = payload(category=category, description=description, tags=tags, associated_host=associated_host)
    result = client(ctx).patch(f"/engagements/{engagement_id}/loot/{file_id}", json=body)
    emit(ctx, result)


@loot_group.command("delete")
@engagement_option
@click.argument("file_id", type=int)
@click.pass_context
def delete(ctx, engagement_id, file_id):
    """Delete a loot file, including its encrypted content."""
    client(ctx).delete(f"/engagements/{engagement_id}/loot/{file_id}")
    success(f"Deleted loot file {file_id}.")
