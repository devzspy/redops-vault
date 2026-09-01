from flask import Blueprint

bp = Blueprint("setup", __name__, url_prefix="/setup")

from app.blueprints.setup import routes  # noqa: E402,F401
