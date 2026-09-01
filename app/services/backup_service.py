import base64
import json
import os
import tempfile
import zipfile
from datetime import date, datetime

from app.extensions import db
from app.models.backup import SCOPE_DATABASE_ONLY, SCOPE_ENGAGEMENT, SCOPE_FULL_VAULT, SCOPE_LOOT_FILES
from app.models.engagement import Engagement
from app.models.loot import LootFile
from app.services import crypto_service


def build_archive(destination):
    """Builds a local zip archive containing the data selected by
    destination.scope (the full vault database, all loot file blobs, or one
    engagement's rows + loot files). Returns the local file path; the caller
    is responsible for deleting it after upload.
    """
    fd, path = tempfile.mkstemp(prefix="redops-backup-", suffix=".zip")
    os.close(fd)
    try:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            if destination.scope in (SCOPE_FULL_VAULT, SCOPE_DATABASE_ONLY):
                _add_database(zf)
            if destination.scope in (SCOPE_FULL_VAULT, SCOPE_LOOT_FILES):
                _add_loot_files(zf)
            if destination.scope == SCOPE_ENGAGEMENT:
                _add_engagement(zf, destination.engagement_id)
                _add_loot_files(zf, engagement_id=destination.engagement_id)
    except Exception:
        os.remove(path)
        raise
    return path


def _add_database(zf):
    """Dumps every table's rows as JSON, walking SQLAlchemy metadata directly
    (dialect-agnostic) rather than copying a single database file — Postgres
    has no equivalent of "the database is one file" the way SQLite does.
    """
    manifest = {}
    for table in db.metadata.sorted_tables:
        rows = [_serialize_mapping(row._mapping) for row in db.session.execute(table.select())]
        manifest[table.name] = rows
    zf.writestr("database/export.json", json.dumps(manifest, indent=2))


def _add_loot_files(zf, engagement_id=None):
    query = LootFile.query
    if engagement_id is not None:
        query = query.filter_by(engagement_id=engagement_id)
    for loot in query.all():
        raw = _read_loot_blob(loot)
        if not raw:
            continue
        arcname = f"loot_storage/{loot.engagement_id}/{loot.id}_{loot.original_filename}.enc"
        zf.writestr(arcname, raw)


def _read_loot_blob(loot):
    """Reads back a loot file's raw (still-encrypted) bytes, whichever
    column they live in -- a Postgres Large Object (content_oid) or the
    SQLite bytea fallback (encrypted_content).
    """
    if loot.content_oid is not None:
        conn = db.session.connection().connection
        return crypto_service.read_large_object_raw(conn, loot.content_oid)
    return loot.encrypted_content


def _add_engagement(zf, engagement_id):
    engagement = Engagement.query.get(engagement_id)
    if engagement is None:
        return

    # Binary columns (encrypted credential secrets) are base64-encoded as-is,
    # still ciphertext under the vault's own encryption key. Loot file bytes
    # are NOT inlined here -- content_oid is just a Large Object reference,
    # not the data itself -- they're written as separate zip entries by the
    # _add_loot_files(zf, engagement_id=...) call in build_archive.
    manifest = {
        "engagement": _serialize_row(engagement),
        "credentials": [_serialize_row(c) for c in engagement.credentials],
        "iocs": [_serialize_row(i) for i in engagement.iocs],
        "infrastructure_nodes": [_serialize_row(n) for n in engagement.infrastructure_nodes],
        "infrastructure_edges": [_serialize_row(e) for e in engagement.infrastructure_edges],
        "killchain_entries": [_serialize_row(k) for k in engagement.killchain_entries],
        "findings": [_serialize_row(f) for f in engagement.findings],
        "activity_log_entries": [_serialize_row(a) for a in engagement.activity_log_entries],
        "todos": [_serialize_row(t) for t in engagement.todos],
        "loot_files": [_serialize_loot_metadata(loot) for loot in engagement.loot_files],
    }
    zf.writestr("engagement/manifest.json", json.dumps(manifest, indent=2))


def _serialize_row(instance):
    mapping = {column.name: getattr(instance, column.name) for column in instance.__table__.columns}
    return _serialize_mapping(mapping)


def _serialize_loot_metadata(loot):
    data = _serialize_row(loot)
    data.pop("content_oid", None)
    data.pop("encrypted_content", None)
    return data


def _serialize_mapping(mapping):
    data = {}
    for key, value in mapping.items():
        if isinstance(value, bytes):
            value = base64.b64encode(value).decode("ascii")
        elif isinstance(value, (datetime, date)):
            value = value.isoformat()
        data[key] = value
    return data
