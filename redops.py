"""RedOps Vault operator CLI entry point.

    python redops.py --help

See cli/main.py for the command group definitions and README.md's "Operator
CLI" section for setup instructions.
"""

import sys

import click

from cli.client import ApiError
from cli.main import cli

if __name__ == "__main__":
    try:
        cli()
    except ApiError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
