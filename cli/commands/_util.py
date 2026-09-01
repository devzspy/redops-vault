"""Small shared helpers for command modules."""

import click

from cli.main import get_client

engagement_option = click.option(
    "--engagement", "-e", "engagement_id", type=int, required=True, help="Engagement ID."
)


def payload(**fields):
    """Drops keys whose value is None, so PATCH-style commands only send the
    fields the user actually passed.
    """
    return {k: v for k, v in fields.items() if v is not None}


def client(ctx):
    return get_client(ctx)
