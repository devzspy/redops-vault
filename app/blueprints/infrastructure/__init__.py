from flask import Blueprint

bp = Blueprint("infrastructure", __name__)

from app.blueprints.infrastructure import routes  # noqa: E402,F401
