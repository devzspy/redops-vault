import click

from cli.commands._util import client, engagement_option, payload
from cli.output import console, emit, success

LIST_COLUMNS = [
    ("ID", "id"),
    ("Title", "title"),
    ("Severity", "severity_label"),
    ("Created", "created_at"),
]


def register(cli):
    cli.add_command(finding_group)


@click.group("finding")
def finding_group():
    """Manage findings."""


@finding_group.command("list")
@engagement_option
@click.pass_context
def list_(ctx, engagement_id):
    """List an engagement's findings."""
    result = client(ctx).get(f"/engagements/{engagement_id}/findings")
    emit(ctx, result, columns=LIST_COLUMNS, list_key="findings")


@finding_group.command("create")
@engagement_option
@click.option("--title", required=True)
@click.option("--severity", required=True, type=click.Choice(["info", "low", "medium", "high", "critical"]))
@click.option("--details", help="HTML/plain-text finding details.")
@click.option("--remediation", help="HTML/plain-text remediation guidance.")
@click.pass_context
def create(ctx, engagement_id, title, severity, details, remediation):
    """Create a finding."""
    body = payload(title=title, severity=severity, details=details, remediation=remediation)
    result = client(ctx).post(f"/engagements/{engagement_id}/findings", json=body)
    emit(ctx, result)


@finding_group.command("get")
@engagement_option
@click.argument("finding_id", type=int)
@click.pass_context
def get(ctx, engagement_id, finding_id):
    """Get one finding."""
    result = client(ctx).get(f"/engagements/{engagement_id}/findings/{finding_id}")
    emit(ctx, result)


@finding_group.command("update")
@engagement_option
@click.argument("finding_id", type=int)
@click.option("--title")
@click.option("--severity", type=click.Choice(["info", "low", "medium", "high", "critical"]))
@click.option("--details")
@click.option("--remediation")
@click.pass_context
def update(ctx, engagement_id, finding_id, title, severity, details, remediation):
    """Update a finding. Only the options you pass are changed."""
    body = payload(title=title, severity=severity, details=details, remediation=remediation)
    result = client(ctx).patch(f"/engagements/{engagement_id}/findings/{finding_id}", json=body)
    emit(ctx, result)


@finding_group.command("delete")
@engagement_option
@click.argument("finding_id", type=int)
@click.pass_context
def delete(ctx, engagement_id, finding_id):
    """Delete a finding."""
    client(ctx).delete(f"/engagements/{engagement_id}/findings/{finding_id}")
    success(f"Deleted finding {finding_id}.")


@finding_group.command("report")
@engagement_option
@click.option("--output", "-o", type=click.Path(dir_okay=False), help="Save to a file instead of printing.")
@click.pass_context
def report(ctx, engagement_id, output):
    """Export the engagement's findings as a Markdown report."""
    text = client(ctx).get_text(f"/engagements/{engagement_id}/findings/report.md")
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(text)
        success(f"Saved report to {output}.")
    else:
        console.print(text, markup=False, highlight=False)
