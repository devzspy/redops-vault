import click

from cli.commands._util import client, engagement_option, payload
from cli.output import emit, success

LIST_COLUMNS = [
    ("ID", "id"),
    ("Label", "display_label"),
    ("Type", "credential_type_label"),
    ("Status", "status_label"),
    ("Host", "source_host"),
]

TYPES = ["password", "api_key", "ssh_key"]
STATUSES = ["untested", "working", "not_working"]


def _secret_options(fn):
    fn = click.option("--username")(fn)
    fn = click.option("--password")(fn)
    fn = click.option("--hash", "hash_")(fn)
    fn = click.option("--secret-api-key", "api_key_secret", help="An API key/token this credential grants access to.")(fn)
    fn = click.option("--ssh-private-key")(fn)
    fn = click.option("--ssh-passphrase")(fn)
    fn = click.option("--totp-secret", help="Base32 TOTP enrollment secret, if this credential has 2FA.")(fn)
    fn = click.option("--domain")(fn)
    fn = click.option("--source-host")(fn)
    fn = click.option("--access-description")(fn)
    fn = click.option("--notes")(fn)
    return fn


def _payload(
    credential_type, status, username, password, hash_, api_key_secret, ssh_private_key, ssh_passphrase,
    totp_secret, domain, source_host, access_description, notes,
):
    return payload(
        credential_type=credential_type,
        status=status,
        username=username,
        password=password,
        hash=hash_,
        api_key=api_key_secret,
        ssh_private_key=ssh_private_key,
        ssh_passphrase=ssh_passphrase,
        totp_secret=totp_secret,
        domain=domain,
        source_host=source_host,
        access_description=access_description,
        notes=notes,
    )


def register(cli):
    cli.add_command(credential_group)


@click.group("credential")
def credential_group():
    """Manage credentials. Secret fields are encrypted at rest (AES-256-GCM)."""


@credential_group.command("list")
@engagement_option
@click.pass_context
def list_(ctx, engagement_id):
    """List an engagement's credentials with secret values masked."""
    result = client(ctx).get(f"/engagements/{engagement_id}/credentials")
    emit(ctx, result, columns=LIST_COLUMNS, list_key="credentials")


@credential_group.command("create")
@engagement_option
@click.option("--type", "credential_type", type=click.Choice(TYPES), default="password")
@click.option("--status", type=click.Choice(STATUSES), default="untested")
@_secret_options
@click.pass_context
def create(
    ctx, engagement_id, credential_type, status, username, password, hash_, api_key_secret, ssh_private_key,
    ssh_passphrase, totp_secret, domain, source_host, access_description, notes,
):
    """Record a credential."""
    body = _payload(
        credential_type, status, username, password, hash_, api_key_secret, ssh_private_key, ssh_passphrase,
        totp_secret, domain, source_host, access_description, notes,
    )
    result = client(ctx).post(f"/engagements/{engagement_id}/credentials", json=body)
    emit(ctx, result)


@credential_group.command("get")
@engagement_option
@click.argument("cred_id", type=int)
@click.option("--reveal", is_flag=True, help="Include decrypted secret values.")
@click.pass_context
def get(ctx, engagement_id, cred_id, reveal):
    """Get a credential."""
    result = client(ctx).get(
        f"/engagements/{engagement_id}/credentials/{cred_id}", params={"reveal": "true" if reveal else "false"}
    )
    emit(ctx, result)


@credential_group.command("update")
@engagement_option
@click.argument("cred_id", type=int)
@click.option("--type", "credential_type", type=click.Choice(TYPES))
@click.option("--status", type=click.Choice(STATUSES))
@_secret_options
@click.pass_context
def update(
    ctx, engagement_id, cred_id, credential_type, status, username, password, hash_, api_key_secret,
    ssh_private_key, ssh_passphrase, totp_secret, domain, source_host, access_description, notes,
):
    """Update a credential. Only the options you pass are changed, except that
    passing any secret field overwrites it entirely (the whole secret set is
    re-encrypted together server-side)."""
    body = _payload(
        credential_type, status, username, password, hash_, api_key_secret, ssh_private_key, ssh_passphrase,
        totp_secret, domain, source_host, access_description, notes,
    )
    result = client(ctx).patch(f"/engagements/{engagement_id}/credentials/{cred_id}", json=body)
    emit(ctx, result)


@credential_group.command("delete")
@engagement_option
@click.argument("cred_id", type=int)
@click.pass_context
def delete(ctx, engagement_id, cred_id):
    """Delete a credential."""
    client(ctx).delete(f"/engagements/{engagement_id}/credentials/{cred_id}")
    success(f"Deleted credential {cred_id}.")


@credential_group.command("totp")
@engagement_option
@click.argument("cred_id", type=int)
@click.pass_context
def totp(ctx, engagement_id, cred_id):
    """Get the current live TOTP code for a credential with a TOTP secret set."""
    result = client(ctx).get(f"/engagements/{engagement_id}/credentials/{cred_id}/totp")
    emit(ctx, result)
