from flask import Blueprint

bp = Blueprint("findings", __name__)

from app.blueprints.findings import routes  # noqa: E402,F401
