from flask import Blueprint

bp = Blueprint("backups", __name__, url_prefix="/backups")

from app.blueprints.backups import routes  # noqa: E402,F401
