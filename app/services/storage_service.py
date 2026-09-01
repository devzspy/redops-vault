from app.extensions import db
from app.services import crypto_service


def _is_postgres():
    return db.engine.dialect.name == "postgresql"


def save_upload(file_stream):
    """Encrypt an uploaded file. Returns (field_updates, file_size_bytes,
    sha256_hex) where field_updates is a dict of LootFile column values to
    apply -- on Postgres the bytes are streamed straight into a new Large
    Object (content_oid set, nothing buffered in memory regardless of file
    size); on SQLite (test-only) they're buffered into encrypted_content,
    matching today's behavior.
    """
    if _is_postgres():
        conn = db.session.connection().connection
        oid, size, sha256_hex = crypto_service.encrypt_to_large_object(conn, file_stream)
        return {"content_oid": oid, "encrypted_content": None}, size, sha256_hex

    encrypted_content, size, sha256_hex = crypto_service.encrypt_stream(file_stream)
    return {"content_oid": None, "encrypted_content": encrypted_content}, size, sha256_hex


def stream_download(loot_file):
    """Generator yielding decrypted plaintext chunks for the given loot file.

    Downloads are wrapped in Flask's stream_with_context, which re-pushes the
    request/app context for the generator's lifetime -- but by the time it
    runs, request teardown has already released whatever connection was
    checked out during the view function itself. So the Large Object path
    must not resolve db.session.connection() until the generator body
    actually starts (i.e. lazily, after that context re-push), or it ends up
    holding a pooled connection object whose underlying DBAPI connection has
    already been returned and detached.
    """
    if loot_file.content_oid is not None:
        oid = loot_file.content_oid

        def _lazy_large_object_stream():
            conn = db.session.connection().connection
            yield from crypto_service.decrypt_from_large_object(conn, oid)

        return _lazy_large_object_stream()
    return crypto_service.decrypt_stream(loot_file.encrypted_content)
