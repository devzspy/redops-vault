import hashlib
import io
import os
import secrets
import struct

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import current_app

MAGIC = b"RVL1"
NONCE_PREFIX_LEN = 8
CHUNK_SIZE = 1024 * 1024  # 1 MiB plaintext per chunk

_key_cache = {}


def ensure_key():
    """Load the file-encryption key from disk, generating one on first run."""
    path = current_app.config["ENCRYPTION_KEY_PATH"]
    if path in _key_cache:
        return _key_cache[path]

    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        key = secrets.token_bytes(32)
        with open(path, "wb") as f:
            f.write(key)
    else:
        with open(path, "rb") as f:
            key = f.read()

    _key_cache[path] = key
    return key


def _chunk_nonce(nonce_prefix, chunk_index):
    return nonce_prefix + struct.pack(">I", chunk_index)


def encrypt_stream(input_stream):
    """Encrypt input_stream (file-like, .read(n)) into a chunked AES-256-GCM
    byte string, ready to store as a DB blob. Returns
    (encrypted_bytes, plaintext_size_bytes, sha256_hex) of the PLAINTEXT.
    """
    key = ensure_key()
    aesgcm = AESGCM(key)
    nonce_prefix = secrets.token_bytes(NONCE_PREFIX_LEN)

    sha256 = hashlib.sha256()
    total_bytes = 0
    chunk_index = 0

    out = io.BytesIO()
    out.write(MAGIC)
    out.write(nonce_prefix)
    while True:
        chunk = input_stream.read(CHUNK_SIZE)
        if not chunk:
            break
        total_bytes += len(chunk)
        sha256.update(chunk)
        nonce = _chunk_nonce(nonce_prefix, chunk_index)
        ciphertext = aesgcm.encrypt(nonce, chunk, None)
        out.write(struct.pack(">I", len(ciphertext)))
        out.write(ciphertext)
        chunk_index += 1

    return out.getvalue(), total_bytes, sha256.hexdigest()


def decrypt_stream(encrypted_bytes):
    """Generator yielding decrypted plaintext chunks from bytes written by
    encrypt_stream. Raises InvalidTag if any chunk fails authentication.
    """
    key = ensure_key()
    aesgcm = AESGCM(key)

    f = io.BytesIO(encrypted_bytes)
    magic = f.read(len(MAGIC))
    if magic != MAGIC:
        raise ValueError("Not a recognized RedOps Vault encrypted file")
    nonce_prefix = f.read(NONCE_PREFIX_LEN)

    chunk_index = 0
    while True:
        length_bytes = f.read(4)
        if not length_bytes:
            break
        if len(length_bytes) != 4:
            raise ValueError("Truncated ciphertext length header")
        (length,) = struct.unpack(">I", length_bytes)
        ciphertext = f.read(length)
        if len(ciphertext) != length:
            raise ValueError("Truncated ciphertext chunk")
        nonce = _chunk_nonce(nonce_prefix, chunk_index)
        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        except InvalidTag:
            raise InvalidTag(
                f"Chunk {chunk_index} failed authentication; file may be corrupted or tampered with"
            )
        yield plaintext
        chunk_index += 1


def encrypt_to_large_object(pg_conn, input_stream):
    """Encrypt input_stream directly into a new Postgres Large Object, using
    the same MAGIC/nonce/chunked-AES-GCM framing as encrypt_stream, but
    writing each chunk to the LO as it's encrypted instead of buffering the
    whole file in memory. Returns (oid, plaintext_size_bytes, sha256_hex).
    """
    key = ensure_key()
    aesgcm = AESGCM(key)
    nonce_prefix = secrets.token_bytes(NONCE_PREFIX_LEN)

    sha256 = hashlib.sha256()
    total_bytes = 0
    chunk_index = 0

    lo = pg_conn.lobject(mode="wb")
    oid = lo.oid
    lo.write(MAGIC)
    lo.write(nonce_prefix)
    while True:
        chunk = input_stream.read(CHUNK_SIZE)
        if not chunk:
            break
        total_bytes += len(chunk)
        sha256.update(chunk)
        nonce = _chunk_nonce(nonce_prefix, chunk_index)
        ciphertext = aesgcm.encrypt(nonce, chunk, None)
        lo.write(struct.pack(">I", len(ciphertext)))
        lo.write(ciphertext)
        chunk_index += 1
    lo.close()

    return oid, total_bytes, sha256.hexdigest()


def decrypt_from_large_object(pg_conn, oid):
    """Generator yielding decrypted plaintext chunks read directly from a
    Postgres Large Object written by encrypt_to_large_object. Same bounded
    memory property on the way out. Raises InvalidTag if any chunk fails
    authentication.
    """
    key = ensure_key()
    aesgcm = AESGCM(key)

    lo = pg_conn.lobject(oid, mode="rb")
    try:
        magic = lo.read(len(MAGIC))
        if magic != MAGIC:
            raise ValueError("Not a recognized RedOps Vault encrypted file")
        nonce_prefix = lo.read(NONCE_PREFIX_LEN)

        chunk_index = 0
        while True:
            length_bytes = lo.read(4)
            if not length_bytes:
                break
            if len(length_bytes) != 4:
                raise ValueError("Truncated ciphertext length header")
            (length,) = struct.unpack(">I", length_bytes)
            ciphertext = lo.read(length)
            if len(ciphertext) != length:
                raise ValueError("Truncated ciphertext chunk")
            nonce = _chunk_nonce(nonce_prefix, chunk_index)
            try:
                plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            except InvalidTag:
                raise InvalidTag(
                    f"Chunk {chunk_index} failed authentication; file may be corrupted or tampered with"
                )
            yield plaintext
            chunk_index += 1
    finally:
        lo.close()


def read_large_object_raw(pg_conn, oid):
    """Reads back the raw (still-encrypted) bytes of a Large Object whole --
    used by backups, which want the ciphertext blob as-is, not decrypted.
    """
    lo = pg_conn.lobject(oid, mode="rb")
    try:
        return lo.read()
    finally:
        lo.close()


def encrypt_field(plaintext):
    """Encrypt a short string field (e.g. a credential password) for storage
    in a LargeBinary column. Returns bytes: 12-byte nonce + ciphertext+tag.
    """
    if plaintext is None:
        return None
    key = ensure_key()
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ciphertext


def decrypt_field(blob):
    """Decrypt a value produced by encrypt_field."""
    if blob is None:
        return None
    key = ensure_key()
    aesgcm = AESGCM(key)
    nonce, ciphertext = blob[:12], blob[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
