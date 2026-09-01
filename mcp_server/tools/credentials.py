from typing import Optional

from mcp_server import client


def _credential_payload(
    credential_type, status, username, password, hash, api_key, ssh_private_key, ssh_passphrase, totp_secret, domain, source_host, access_description, notes
):
    return {
        k: v
        for k, v in {
            "credential_type": credential_type,
            "status": status,
            "username": username,
            "password": password,
            "hash": hash,
            "api_key": api_key,
            "ssh_private_key": ssh_private_key,
            "ssh_passphrase": ssh_passphrase,
            "totp_secret": totp_secret,
            "domain": domain,
            "source_host": source_host,
            "access_description": access_description,
            "notes": notes,
        }.items()
        if v is not None
    }


def register(mcp):
    @mcp.tool()
    def credential_list(engagement_id: int) -> dict:
        """List an engagement's credentials with secret values masked (has_password
        etc. booleans only). Use credential_get(..., reveal=True) or
        credential_create/update's response to see actual secret values."""
        return client.get(f"/engagements/{engagement_id}/credentials")

    @mcp.tool()
    def credential_create(
        engagement_id: int,
        credential_type: str = "password",
        username: Optional[str] = None,
        password: Optional[str] = None,
        hash: Optional[str] = None,
        api_key: Optional[str] = None,
        ssh_private_key: Optional[str] = None,
        ssh_passphrase: Optional[str] = None,
        totp_secret: Optional[str] = None,
        domain: Optional[str] = None,
        source_host: Optional[str] = None,
        access_description: Optional[str] = None,
        status: str = "untested",
        notes: Optional[str] = None,
    ) -> dict:
        """Record a credential. credential_type is one of: password, api_key,
        ssh_key. status is one of: untested, working, not_working. All
        secret fields are encrypted at rest (AES-256-GCM). totp_secret is a
        base32 TOTP enrollment secret, if this credential has 2FA."""
        payload = _credential_payload(
            credential_type, status, username, password, hash, api_key, ssh_private_key, ssh_passphrase,
            totp_secret, domain, source_host, access_description, notes,
        )
        return client.post(f"/engagements/{engagement_id}/credentials", json=payload)

    @mcp.tool()
    def credential_get(engagement_id: int, cred_id: int, reveal: bool = False) -> dict:
        """Get a credential. Pass reveal=True to include decrypted secret values
        (password, hash, api_key, ssh_private_key, ssh_passphrase, totp_secret)."""
        return client.get(f"/engagements/{engagement_id}/credentials/{cred_id}", params={"reveal": "true" if reveal else "false"})

    @mcp.tool()
    def credential_update(
        engagement_id: int,
        cred_id: int,
        credential_type: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        hash: Optional[str] = None,
        api_key: Optional[str] = None,
        ssh_private_key: Optional[str] = None,
        ssh_passphrase: Optional[str] = None,
        totp_secret: Optional[str] = None,
        domain: Optional[str] = None,
        source_host: Optional[str] = None,
        access_description: Optional[str] = None,
        status: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """Update a credential. Submitting any secret field (password, hash,
        api_key, ssh_private_key, ssh_passphrase, totp_secret) overwrites it
        -- there's no partial update of a single secret while leaving the
        others untouched, since the whole set is re-encrypted together."""
        payload = _credential_payload(
            credential_type, status, username, password, hash, api_key, ssh_private_key, ssh_passphrase,
            totp_secret, domain, source_host, access_description, notes,
        )
        return client.patch(f"/engagements/{engagement_id}/credentials/{cred_id}", json=payload)

    @mcp.tool()
    def credential_delete(engagement_id: int, cred_id: int) -> dict:
        """Delete a credential."""
        return client.delete(f"/engagements/{engagement_id}/credentials/{cred_id}")

    @mcp.tool()
    def credential_totp(engagement_id: int, cred_id: int) -> dict:
        """Get the current live TOTP code for a credential that has a TOTP
        secret set, plus seconds remaining before it rotates."""
        return client.get(f"/engagements/{engagement_id}/credentials/{cred_id}/totp")
