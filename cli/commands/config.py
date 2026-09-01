import click

from cli import config as cfg
from cli.client import ApiClient, ApiError
from cli.output import success


def register(cli):
    cli.add_command(config_group)


@click.group("config")
def config_group():
    """Manage the locally saved API base URL and API key."""


@config_group.command("set-url")
@click.argument("base_url")
def set_url(base_url):
    """Save the API base URL (e.g. http://localhost:5000/api/v1)."""
    cfg.set_value("api_base_url", base_url.rstrip("/"))
    success(f"Saved base URL to {cfg.config_path()}")


@config_group.command("set-key")
@click.argument("api_key")
def set_key(api_key):
    """Save an API key (create one at /api-keys in the web UI)."""
    cfg.set_value("api_key", api_key)
    success(f"Saved API key to {cfg.config_path()}")


@config_group.command("show")
def show():
    """Show the resolved base URL and a masked API key."""
    data = cfg.load()
    base_url, api_key = cfg.resolve()
    click.echo(f"Config file:  {cfg.config_path()}")
    click.echo(f"Base URL:     {base_url}")
    if api_key:
        masked = api_key[:7] + "..." + api_key[-4:] if len(api_key) > 11 else "***"
        click.echo(f"API key:      {masked}")
    else:
        click.echo("API key:      (not set)")
    if not data:
        click.echo("\n(no local config file yet -- using env vars / defaults)")


@config_group.command("test")
@click.pass_context
def test(ctx):
    """Verify the configured base URL and API key work by listing engagements."""
    base_url, api_key = ctx.obj["base_url"], ctx.obj["api_key"]
    if not api_key:
        raise click.ClickException("No API key configured. Run `redops config set-key <key>` first.")
    client = ApiClient(base_url, api_key)
    try:
        result = client.get("/engagements")
    except ApiError as exc:
        raise click.ClickException(f"Connection to {base_url} failed: {exc}") from exc
    finally:
        client.close()
    count = len(result.get("engagements", []))
    success(f"Connected to {base_url} -- API key is valid ({count} engagement(s) visible).")
