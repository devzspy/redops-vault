from flask import Blueprint

bp = Blueprint("loot", __name__)

from app.blueprints.loot import routes  # noqa: E402,F401
