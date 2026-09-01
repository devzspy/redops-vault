from flask import Blueprint

bp = Blueprint("api_keys", __name__, url_prefix="/api-keys")

from app.blueprints.api_keys import routes  # noqa: E402,F401
