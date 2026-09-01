"""Restores data from a backup archive built by backup_service.build_archive.

Two modes:
  - restore_full_archive: wipes and reloads the ENTIRE database from a
    full_vault/database_only-scoped archive's database/export.json, plus
    any loot file blobs (loot_storage/) the same archive contains. This is
    a point-in-time restore -- anything in the current database that isn't
    in the archive (including tables that didn't exist yet when an older
    backup was taken) ends up empty, not merged.
  - restore_loot_only: re-attaches loot file blobs from a loot_files-scoped
    archive to EXISTING loot_files rows in the current database, matched
    by id. Doesn't touch any table row -- for the narrower case of loot
    storage having been lost/corrupted while the database itself is fine.

Engagement-scoped archives (engagement/manifest.json) aren't supported
here -- merging a single engagement's rows back into a live database with
its own ID space is a different, much fuzzier operation than a
point-in-time restore. Those archives can still be downloaded, just not
auto-restored.

Both modes run as one database transaction: any failure rolls back
everything, leaving the database exactly as it was before the attempt.

Known limitation: Large Objects backing loot files before a restore are
orphaned, not deleted -- freeing that space is a manual VACUUM concern,
out of scope here.
"""

import json
import zipfile
from base64 import b64decode
from datetime import date, datetime

from sqlalchemy import Date, DateTime, LargeBinary

from app.extensions import db
from app.services import crypto_service


class RestoreError(Exception):
    """Raised when an archive can't be restored (wrong shape, corrupt, etc.)."""


def _is_postgres():
    return db.engine.dialect.name == "postgresql"


def _open_zip(local_path):
    try:
        return zipfile.ZipFile(local_path)
    except zipfile.BadZipFile as exc:
        raise RestoreError("Not a valid backup archive (corrupt or not a zip file).") from exc


def _extract_loot_blobs(zf):
    """Maps loot_files.id -> raw (still-encrypted) bytes, parsed from
    loot_storage/{engagement_id}/{loot_id}_{filename}.enc entries.
    """
    blobs = {}
    for name in zf.namelist():
        if not name.startswith("loot_storage/") or name.endswith("/"):
            continue
        basename = name.rsplit("/", 1)[-1]
        loot_id_str = basename.split("_", 1)[0]
        if loot_id_str.isdigit():
            blobs[int(loot_id_str)] = zf.read(name)
    return blobs


def inspect_archive(local_path):
    """Reads (without applying) what an archive contains, for a
    confirmation screen before restoring.
    """
    with _open_zip(local_path) as zf:
        names = zf.namelist()
        has_database = "database/export.json" in names
        has_engagement_manifest = "engagement/manifest.json" in names
        loot_blobs = _extract_loot_blobs(zf)

        table_counts = {}
        if has_database:
            manifest = json.loads(zf.read("database/export.json"))
            table_counts = {table: len(rows) for table, rows in manifest.items()}

        engagement_name = None
        if has_engagement_manifest:
            manifest = json.loads(zf.read("engagement/manifest.json"))
            engagement_name = (manifest.get("engagement") or {}).get("name")

    return {
        "has_database": has_database,
        "has_engagement_manifest": has_engagement_manifest,
        "engagement_name": engagement_name,
        "loot_file_count": len(loot_blobs),
        "table_counts": table_counts,
        "can_restore_full": has_database,
        "can_restore_loot_only": not has_database and not has_engagement_manifest and bool(loot_blobs),
    }


def _deserialize_value(value, col_type):
    if value is None:
        return None
    if isinstance(col_type, LargeBinary):
        return b64decode(value)
    if isinstance(col_type, DateTime):
        return datetime.fromisoformat(value)
    if isinstance(col_type, Date):
        return date.fromisoformat(value)
    return value


def _self_referential_columns(table):
    """Column names on `table` that FK-reference `table` itself (e.g.
    attack_techniques.parent_technique_id) -- these need a two-pass insert
    since a row can reference another row in the same not-yet-fully-loaded
    batch, in either order.
    """
    return [fk.parent.name for fk in table.foreign_keys if fk.column.table is table]


def restore_full_archive(local_path):
    """Wipes and reloads the entire database from a full-database export,
    then restores any loot file blobs the archive also contains. Returns a
    summary dict: {"tables": {name: row_count}, "loot_files_restored": N,
    "loot_files_in_archive": N}.
    """
    with _open_zip(local_path) as zf:
        if "database/export.json" not in zf.namelist():
            raise RestoreError("This archive doesn't contain a full database export.")
        manifest = json.loads(zf.read("database/export.json"))
        loot_blobs = _extract_loot_blobs(zf)

    table_order = db.metadata.sorted_tables  # parents before children
    tables_by_name = {t.name: t for t in table_order}

    try:
        if _is_postgres():
            table_list = ", ".join(f'"{t.name}"' for t in table_order)
            db.session.execute(db.text(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE"))
        else:
            for table in reversed(table_order):
                db.session.execute(table.delete())

        row_counts = {}
        for table in table_order:
            rows = manifest.get(table.name)
            if not rows:
                row_counts[table.name] = 0
                continue

            self_ref_cols = _self_referential_columns(table)
            deferred = []
            prepared_rows = []
            for raw_row in rows:
                row = {col.name: _deserialize_value(raw_row.get(col.name), col.type) for col in table.columns}
                if table.name == "loot_files":
                    # Old Large Object / bytea references are meaningless in a
                    # fresh restore -- blobs are reattached by id below.
                    row["content_oid"] = None
                    row["encrypted_content"] = None
                for col_name in self_ref_cols:
                    if row.get(col_name) is not None:
                        deferred.append((row["id"], col_name, row[col_name]))
                        row[col_name] = None
                prepared_rows.append(row)

            db.session.execute(table.insert(), prepared_rows)
            for row_id, col_name, value in deferred:
                db.session.execute(table.update().where(table.c.id == row_id).values(**{col_name: value}))
            row_counts[table.name] = len(prepared_rows)

            if _is_postgres() and "id" in table.c:
                max_id = db.session.execute(db.text(f'SELECT MAX(id) FROM "{table.name}"')).scalar()
                if max_id is not None:
                    db.session.execute(
                        db.text("SELECT setval(pg_get_serial_sequence(:t, 'id'), :v)"), {"t": table.name, "v": max_id}
                    )

        loot_files_table = tables_by_name.get("loot_files")
        loot_restored = 0
        if loot_blobs and loot_files_table is not None:
            conn = db.session.connection().connection if _is_postgres() else None
            for loot_id, raw_bytes in loot_blobs.items():
                if _is_postgres():
                    oid = crypto_service.write_large_object_raw(conn, raw_bytes)
                    values = {"content_oid": oid}
                else:
                    values = {"encrypted_content": raw_bytes}
                result = db.session.execute(
                    loot_files_table.update().where(loot_files_table.c.id == loot_id).values(**values)
                )
                if result.rowcount:
                    loot_restored += 1

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return {"tables": row_counts, "loot_files_restored": loot_restored, "loot_files_in_archive": len(loot_blobs)}


def restore_loot_only(local_path):
    """Re-attaches loot file blobs from an archive to existing loot_files
    rows in the current database, matched by id. Doesn't touch any other
    table or row.
    """
    with _open_zip(local_path) as zf:
        loot_blobs = _extract_loot_blobs(zf)
    if not loot_blobs:
        raise RestoreError("This archive doesn't contain any loot file blobs.")

    from app.models.loot import LootFile

    restored = 0
    skipped = 0
    try:
        for loot_id, raw_bytes in loot_blobs.items():
            loot = LootFile.query.get(loot_id)
            if loot is None:
                skipped += 1
                continue
            if _is_postgres():
                conn = db.session.connection().connection
                loot.content_oid = crypto_service.write_large_object_raw(conn, raw_bytes)
                loot.encrypted_content = None
            else:
                loot.encrypted_content = raw_bytes
                loot.content_oid = None
            restored += 1
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return {"restored": restored, "skipped": skipped, "total_in_archive": len(loot_blobs)}
