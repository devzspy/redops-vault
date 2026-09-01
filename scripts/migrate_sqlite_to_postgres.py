"""One-off script: copy data from the old SQLite-based redops-vault database
(with on-disk encrypted loot files) into a Postgres database.

The target Postgres database must already have the schema applied (run the
app once against it, or `flask db upgrade`, before running this script).

Ciphertext is copied byte-for-byte -- the encryption key is unchanged, so
there is no decrypt/recrypt step. `loot_files` is handled specially: the old
schema pointed at an on-disk `<storage_uuid>.enc` file instead of storing
bytes in the row, so this script reads that file and writes its bytes into a
new Postgres Large Object, storing the resulting oid in `content_oid`.

Usage:
    DATABASE_URL=postgresql://user:pass@localhost:5432/redops_vault \\
        .venv/Scripts/python.exe scripts/migrate_sqlite_to_postgres.py

Run this against a throwaway Postgres first and check the printed row
counts / spot-decrypt output before ever pointing it at a database you
intend to keep. It never modifies or deletes the source SQLite database or
loot_storage directory.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import MetaData, create_engine, select

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sqlite-path",
        default=os.path.join(REPO_ROOT, "instance", "redops_vault.db"),
        help="Path to the old SQLite database file.",
    )
    parser.add_argument(
        "--loot-storage-dir",
        default=os.path.join(REPO_ROOT, "instance", "loot_storage"),
        help="Path to the old on-disk loot_storage directory.",
    )
    parser.add_argument(
        "--target-url",
        default=os.environ.get("DATABASE_URL"),
        help="Postgres URL to migrate into. Defaults to $DATABASE_URL.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Proceed even if the target database already has rows in it.",
    )
    return parser.parse_args()


def _reflect_source(sqlite_path):
    if not os.path.exists(sqlite_path):
        raise SystemExit(f"Source SQLite database not found: {sqlite_path}")
    engine = create_engine(f"sqlite:///{sqlite_path}")
    metadata = MetaData()
    metadata.reflect(bind=engine)
    return engine, metadata


def _reset_postgres_sequence(conn, table_name):
    """After a bulk copy with explicit primary keys, the table's identity
    sequence still thinks it's at 1 -- point it at the real max id so the
    next app-created row doesn't collide.
    """
    conn.exec_driver_sql(
        f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
        f"COALESCE((SELECT MAX(id) FROM {table_name}), 1), "
        f"(SELECT MAX(id) IS NOT NULL FROM {table_name}))"
    )


def _migrate_loot_files(source_conn, source_table, target_table, target_conn, loot_dir):
    rows = source_conn.execute(select(source_table)).mappings().all()
    to_insert = []
    missing = []
    raw_pg_conn = target_conn.connection
    for row in rows:
        data = {k: v for k, v in row.items() if k != "storage_uuid"}
        path = os.path.join(loot_dir, str(row["engagement_id"]), f"{row['storage_uuid']}.enc")
        if not os.path.exists(path):
            missing.append((row["id"], path))
            continue
        with open(path, "rb") as f:
            content = f.read()
        lo = raw_pg_conn.lobject(mode="wb")
        lo.write(content)
        lo.close()
        data["content_oid"] = lo.oid
        data["encrypted_content"] = None
        to_insert.append(data)

    if missing:
        print(f"  WARNING: {len(missing)} loot_files missing on-disk ciphertext, skipped:")
        for loot_id, path in missing:
            print(f"    loot_files.id={loot_id} -> {path}")

    if to_insert:
        target_conn.execute(target_table.insert(), to_insert)
    return len(to_insert)


def _migrate_generic_table(source_conn, source_table, target_table, target_conn):
    source_cols = {c.name for c in source_table.columns}
    target_cols = {c.name for c in target_table.columns}
    common_cols = [c for c in source_cols & target_cols]
    if not common_cols:
        return 0

    rows = source_conn.execute(select(*[source_table.c[c] for c in common_cols])).mappings().all()
    if not rows:
        return 0

    to_insert = [dict(row) for row in rows]
    target_conn.execute(target_table.insert(), to_insert)
    return len(to_insert)


def _spot_check(target_conn, target_db_metadata):
    """Decrypt a handful of migrated rows to confirm ciphertext survived
    intact -- "the copy didn't throw" is not the same as "the bytes are
    still decryptable with our key". Needs a Flask app context because
    crypto_service reads the encryption key path from current_app.config.
    """
    from flask import Flask

    from app.services import crypto_service

    spot_app = Flask(__name__, instance_relative_config=True)
    spot_app.config.from_object("config.Config")

    with spot_app.app_context():
        credentials = target_db_metadata.tables.get("credentials")
        if credentials is not None:
            row = target_conn.execute(select(credentials).limit(1)).mappings().first()
            if row and row.get("password_encrypted"):
                plaintext = crypto_service.decrypt_field(row["password_encrypted"])
                print(f"  spot-check: credentials.id={row['id']} password decrypts OK ({len(plaintext)} chars)")

        loot_files = target_db_metadata.tables.get("loot_files")
        if loot_files is not None:
            row = target_conn.execute(select(loot_files).limit(1)).mappings().first()
            if row and row.get("content_oid") is not None:
                raw_pg_conn = target_conn.connection
                total = sum(
                    len(chunk)
                    for chunk in crypto_service.decrypt_from_large_object(raw_pg_conn, row["content_oid"])
                )
                print(f"  spot-check: loot_files.id={row['id']} decrypts OK ({total} plaintext bytes)")


def main():
    args = parse_args()
    if not args.target_url:
        raise SystemExit("No target Postgres URL given (pass --target-url or set DATABASE_URL).")

    os.environ["DATABASE_URL"] = args.target_url

    from app import models  # noqa: F401  (registers models with SQLAlchemy metadata)
    from app.extensions import db as target_db_module

    target_metadata = target_db_module.metadata

    source_engine, source_metadata = _reflect_source(args.sqlite_path)
    target_engine = create_engine(args.target_url)

    with target_engine.connect() as target_conn:
        if not args.force:
            for table in target_metadata.sorted_tables:
                count = target_conn.execute(select(table)).first()
                if count is not None:
                    raise SystemExit(
                        f"Target table '{table.name}' already has rows. "
                        "Pass --force to migrate into it anyway."
                    )
            target_conn.rollback()

        with source_engine.connect() as source_conn, target_conn.begin():
            for table in target_metadata.sorted_tables:
                name = table.name
                if name not in source_metadata.tables:
                    print(f"{name}: not present in source, skipping")
                    continue
                source_table = source_metadata.tables[name]

                if name == "loot_files":
                    count = _migrate_loot_files(
                        source_conn, source_table, table, target_conn, args.loot_storage_dir
                    )
                else:
                    count = _migrate_generic_table(source_conn, source_table, table, target_conn)

                if count and target_engine.dialect.name == "postgresql" and "id" in table.columns:
                    _reset_postgres_sequence(target_conn, name)

                print(f"{name}: copied {count} rows")

        print("\nSpot-checking decryption of migrated ciphertext:")
        _spot_check(target_conn, target_metadata)

    print("\nDone. Source SQLite database and loot_storage directory were not modified.")


if __name__ == "__main__":
    main()
