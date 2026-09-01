"""Local CLI config file (~/.config/redops-vault/config.json or platform
equivalent via click.get_app_dir), plus environment variable and CLI flag
overrides. Resolution order for both settings is: explicit flag > env var >
config file > default.
"""

import json
import os
from pathlib import Path

import click

APP_NAME = "redops-vault"
ENV_BASE_URL = "REDOPS_API_BASE_URL"
ENV_API_KEY = "REDOPS_API_KEY"
DEFAULT_BASE_URL = "http://localhost:5000/api/v1"


def config_path():
    return Path(click.get_app_dir(APP_NAME)) / "config.json"


def load():
    path = config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save(data):
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # chmod isn't meaningful on Windows; the file still lives under the user's profile


def set_value(key, value):
    data = load()
    data[key] = value
    save(data)


def resolve(base_url_override=None, api_key_override=None):
    stored = load()
    base_url = base_url_override or os.environ.get(ENV_BASE_URL) or stored.get("api_base_url") or DEFAULT_BASE_URL
    api_key = api_key_override or os.environ.get(ENV_API_KEY) or stored.get("api_key")
    return base_url, api_key
