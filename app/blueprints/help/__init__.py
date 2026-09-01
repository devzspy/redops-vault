from flask import Blueprint

bp = Blueprint("help", __name__, url_prefix="/help")

from app.blueprints.help import routes  # noqa: E402,F401
