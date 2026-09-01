"""Shared helpers for the /api/v1 JSON blueprints.

Error responses reuse the app's normal `abort(status, description=...)`
idiom -- the same one the HTML routes already use -- rather than inventing
a parallel mechanism. `app/__init__.py::_register_error_handlers` renders
those as JSON instead of an HTML error page for any request under
/api/v1/, so a plain `abort(400, description="...")` or
`Model.query.get_or_404()` here already does the right thing.
"""

from datetime import datetime

from flask import abort, request


def json_body():
    """The parsed JSON request body as a dict, or {} if absent/invalid."""
    return request.get_json(silent=True) or {}


def require_fields(data, *names):
    """Aborts 400 if any of `names` is missing or blank in `data`."""
    missing = [name for name in names if not data.get(name)]
    if missing:
        abort(400, description=f"Missing required field(s): {', '.join(missing)}")


def require_choice(value, choices, field_name):
    """Aborts 400 if `value` isn't one of `choices` (value may be None/blank
    only if that's itself a valid choice).
    """
    if value not in choices:
        abort(400, description=f"Invalid {field_name}")


def pagination_args(default_per_page=20):
    page = request.args.get("page", 1, type=int) or 1
    per_page = request.args.get("per_page", default_per_page, type=int) or default_per_page
    return page, per_page


def parse_datetime(value):
    """Parses an ISO 8601 datetime string (JSON callers aren't held to the
    HTML forms' stricter `%Y-%m-%dT%H:%M`/`%Y-%m-%d` input formats).
    Returns None for a blank/invalid value.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def str_or_none(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None
