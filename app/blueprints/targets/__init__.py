from flask import Blueprint

bp = Blueprint("targets", __name__)

from app.blueprints.targets import routes  # noqa: E402,F401
