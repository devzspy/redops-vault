import base64

from app.services import totp_service


def test_generate_totp_matches_rfc6238_vector():
    # RFC 6238 Appendix B test vector: ASCII secret "12345678901234567890",
    # SHA-1, T=59 -> counter=1 -> 8-digit code "94287082". Truncating to
    # 6 digits (mod 10^6) gives the same result as computing mod 10^6 directly.
    secret_b32 = base64.b32encode(b"12345678901234567890").decode()
    assert totp_service.generate_totp(secret_b32, timestamp=59) == "287082"


def test_generate_totp_changes_with_time_step():
    secret_b32 = base64.b32encode(b"12345678901234567890").decode()
    code_a = totp_service.generate_totp(secret_b32, timestamp=59)
    code_b = totp_service.generate_totp(secret_b32, timestamp=59 + 30)
    assert code_a != code_b


def test_generate_totp_accepts_lowercase_and_spaced_secret():
    secret_b32 = base64.b32encode(b"12345678901234567890").decode()
    spaced = " ".join(secret_b32.lower()[i : i + 4] for i in range(0, len(secret_b32), 4))
    assert totp_service.generate_totp(spaced, timestamp=59) == "287082"


def test_generate_totp_returns_none_for_invalid_secret():
    assert totp_service.generate_totp("not valid base32!!!") is None
    assert totp_service.generate_totp("") is None
    assert totp_service.generate_totp(None) is None


def test_is_valid_secret():
    secret_b32 = base64.b32encode(b"12345678901234567890").decode()
    assert totp_service.is_valid_secret(secret_b32) is True
    assert totp_service.is_valid_secret("not valid base32!!!") is False
    assert totp_service.is_valid_secret("") is False


def test_seconds_remaining_within_period():
    remaining = totp_service.seconds_remaining(timestamp=59)
    assert remaining == 1  # 59 % 30 == 29, 30 - 29 == 1

    remaining = totp_service.seconds_remaining(timestamp=60)
    assert remaining == 30
