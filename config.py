import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    INSTANCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance")
    DATABASE_FILENAME = os.environ.get("DATABASE_FILENAME", "redops_vault.db")

    _database_url = os.environ.get("DATABASE_URL")
    if _database_url:
        # SQLAlchemy 2.x rejects the legacy "postgres://" scheme some hosts
        # (e.g. Heroku-style providers) still hand out.
        if _database_url.startswith("postgres://"):
            _database_url = "postgresql://" + _database_url[len("postgres://"):]
        SQLALCHEMY_DATABASE_URI = _database_url
    else:
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(INSTANCE_DIR, DATABASE_FILENAME)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ENCRYPTION_KEY_PATH = os.path.join(INSTANCE_DIR, "encryption.key")

    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_COOKIE_SECURE = os.environ.get("JWT_COOKIE_SECURE", "false").lower() == "true"
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_CSRF_CHECK_FORM = True
    JWT_ACCESS_TOKEN_EXPIRES = 60 * 60 * 8  # 8 hours

    # Loot files stream into a Postgres Large Object (up to 4 TB), so this is
    # just a sanity cap on a single upload, not a storage-layer limit.
    MAX_CONTENT_LENGTH = 1024 * 1024 * 1024 * 20  # 20 GiB

    MITRE_ATTACK_URL = (
        "https://raw.githubusercontent.com/mitre/cti/master/"
        "enterprise-attack/enterprise-attack.json"
    )
