import base64
import binascii
import hashlib
import hmac
import struct
import time

PERIOD_SECONDS = 30
DIGITS = 6


def _decode_secret(secret):
    """Normalizes and base32-decodes a TOTP secret (as typically shown in an
    enrollment QR code). Returns None if it isn't valid base32.
    """
    cleaned = secret.strip().replace(" ", "").upper()
    if not cleaned:
        return None
    cleaned += "=" * ((-len(cleaned)) % 8)
    try:
        return base64.b32decode(cleaned)
    except (binascii.Error, ValueError):
        return None


def generate_totp(secret, timestamp=None):
    """Generates the current RFC 6238 TOTP code (HMAC-SHA1, 6 digits, 30s
    step) for a base32 secret. Returns None if the secret isn't valid base32.
    """
    if not secret:
        return None
    key = _decode_secret(secret)
    if key is None:
        return None

    if timestamp is None:
        timestamp = time.time()
    counter = int(timestamp // PERIOD_SECONDS)
    counter_bytes = struct.pack(">Q", counter)
    digest = hmac.new(key, counter_bytes, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    truncated = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    code = truncated % (10**DIGITS)
    return str(code).zfill(DIGITS)


def seconds_remaining(timestamp=None):
    """Seconds left in the current TOTP step, for a countdown UI."""
    if timestamp is None:
        timestamp = time.time()
    return PERIOD_SECONDS - (int(timestamp) % PERIOD_SECONDS)


def is_valid_secret(secret):
    return bool(secret) and _decode_secret(secret) is not None
