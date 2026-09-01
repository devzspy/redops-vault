import hashlib
import secrets


def generate_key():
    """Generate a new API key. Returns (plaintext_token, key_hash, key_prefix).

    Only key_hash should ever be persisted - the plaintext token is shown to
    the user once, at creation time, and cannot be recovered afterward.
    """
    token = "rov_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, key_hash, token[:12]
