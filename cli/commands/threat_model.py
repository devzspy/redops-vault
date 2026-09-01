import click

from cli.commands._util import client, engagement_option
from cli.output import emit


def register(cli):
    cli.add_command(threat_model_group)


@click.group("threat-model")
def threat_model_group():
    """Manage an engagement's threat model / attack plan / objectives document."""


@threat_model_group.command("get")
@engagement_option
@click.pass_context
def get(ctx, engagement_id):
    """Get an engagement's threat model document."""
    result = client(ctx).get(f"/engagements/{engagement_id}/threat-model")
    emit(ctx, result)


@threat_model_group.command("set")
@engagement_option
@click.option("--threat-model", help="HTML/plain-text threat model content.")
@click.option("--attack-plan", help="HTML/plain-text attack plan content.")
@click.option("--objectives", help="HTML/plain-text objectives content.")
@click.pass_context
def set_(ctx, engagement_id, threat_model, attack_plan, objectives):
    """Save (fully overwrite) an engagement's threat model document.

    This is a full replace, not a partial update -- any of the three fields
    you omit is cleared, not left unchanged.
    """
    body = {
        "threat_model": threat_model or "",
        "attack_plan": attack_plan or "",
        "objectives": objectives or "",
    }
    result = client(ctx).put(f"/engagements/{engagement_id}/threat-model", json=body)
    emit(ctx, result)
