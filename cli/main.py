"""Top-level `redops` command group. Wires up global --base-url/--api-key/
--json options and registers every resource subcommand group. Run via
`python redops.py ...` (see redops.py at the repo root).
"""

import click

from cli import config as cfg
from cli.client import ApiClient


@click.group()
@click.option("--base-url", default=None, envvar=cfg.ENV_BASE_URL, help="RedOps Vault API base URL.")
@click.option("--api-key", default=None, envvar=cfg.ENV_API_KEY, help="API key (rov_...). Overrides saved config.")
@click.option("--json", "json_output", is_flag=True, help="Print raw JSON instead of formatted tables.")
@click.pass_context
def cli(ctx, base_url, api_key, json_output):
    """RedOps Vault operator CLI.

    Drives the same /api/v1 API the web UI and MCP server use, so anything
    you can do in the browser (aside from Admin and Backups, which stay
    human/web-only) you can do from here too.

    Needs an API key: create one at /api-keys in the web UI for an
    agent/operator/admin-role user, then either export REDOPS_API_KEY or run
    `redops config set-key rov_...` to save it locally.
    """
    ctx.ensure_object(dict)
    resolved_base_url, resolved_api_key = cfg.resolve(base_url, api_key)
    ctx.obj["json"] = json_output
    ctx.obj["base_url"] = resolved_base_url
    ctx.obj["api_key"] = resolved_api_key
    ctx.obj["_client"] = None


def get_client(ctx):
    """Lazily builds the ApiClient on first use, so `redops config ...`
    subcommands work fine even with no API key configured yet.
    """
    if ctx.obj["_client"] is None:
        if not ctx.obj["api_key"]:
            raise click.ClickException(
                "No API key configured. Run `redops config set-key <key>`, set REDOPS_API_KEY, "
                "or pass --api-key. Create a key at /api-keys in the web UI."
            )
        ctx.obj["_client"] = ApiClient(ctx.obj["base_url"], ctx.obj["api_key"])
    return ctx.obj["_client"]


from cli.commands import (  # noqa: E402
    activity,
    attack,
    config as config_cmd,
    credential,
    engagement,
    finding,
    infra,
    ioc,
    killchain,
    loot,
    target,
    threat_model,
    todo,
)

for module in (
    config_cmd,
    engagement,
    finding,
    loot,
    credential,
    killchain,
    infra,
    target,
    ioc,
    threat_model,
    todo,
    attack,
    activity,
):
    module.register(cli)


def main():
    cli()


if __name__ == "__main__":
    main()
