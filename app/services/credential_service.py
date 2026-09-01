from app.models.loot import CRED_TYPE_PASSWORD, CREDENTIAL_STATUSES, CREDENTIAL_TYPES
from app.services import crypto_service, totp_service

SECRET_FIELDS = ("password", "hash", "api_key", "ssh_private_key", "ssh_passphrase")


def apply_fields(credential, data):
    """Validates and applies submitted credential fields onto `credential`
    in place. `data` is a plain dict (a parsed request.form or JSON body)
    with the same keys as the credential form: credential_type, status,
    totp_secret, username, password, hash, api_key, ssh_private_key,
    ssh_passphrase, domain, source_host, access_description, notes.

    Raises ValueError (a hard client error -- callers should respond 400)
    if credential_type/status is invalid. Returns a recoverable error
    message string if the TOTP secret isn't valid base32 (nothing is
    applied in either failure case), or None on success. Submitting a
    secret field always overwrites it -- there is no partial-update of a
    single secret field while leaving others untouched.
    """
    credential_type = data.get("credential_type") or CRED_TYPE_PASSWORD
    if credential_type not in CREDENTIAL_TYPES:
        raise ValueError("Invalid credential type")

    status = data.get("status") or CREDENTIAL_STATUSES[0]
    if status not in CREDENTIAL_STATUSES:
        raise ValueError("Invalid status")

    totp_secret = (data.get("totp_secret") or "").strip()
    if totp_secret and not totp_service.is_valid_secret(totp_secret):
        return "TOTP secret must be a valid base32 string."

    credential.credential_type = credential_type
    credential.status = status
    credential.username = (data.get("username") or "").strip() or None
    for field in SECRET_FIELDS:
        value = (data.get(field) or "").strip()
        setattr(credential, f"{field}_encrypted", crypto_service.encrypt_field(value) if value else None)
    credential.totp_secret_encrypted = crypto_service.encrypt_field(totp_secret) if totp_secret else None
    credential.domain = (data.get("domain") or "").strip() or None
    credential.source_host = (data.get("source_host") or "").strip() or None
    credential.access_description = (data.get("access_description") or "").strip() or None
    credential.notes = (data.get("notes") or "").strip() or None
    return None


def decrypt(credential):
    """Decrypts every secret field on `credential`. Returns a dict with the
    same keys as SECRET_FIELDS plus totp_secret.
    """
    decrypted = {field: crypto_service.decrypt_field(getattr(credential, f"{field}_encrypted")) for field in SECRET_FIELDS}
    decrypted["totp_secret"] = crypto_service.decrypt_field(credential.totp_secret_encrypted)
    return decrypted


def empty_decrypted():
    return {field: None for field in (*SECRET_FIELDS, "totp_secret")}


def totp_status(credential):
    """Returns {"code", "seconds_remaining"} for a credential's live TOTP
    code, or None if it has no TOTP secret set.
    """
    secret = crypto_service.decrypt_field(credential.totp_secret_encrypted)
    if not secret:
        return None
    code = totp_service.generate_totp(secret)
    if code is None:
        return None
    return {"code": code, "seconds_remaining": totp_service.seconds_remaining()}
