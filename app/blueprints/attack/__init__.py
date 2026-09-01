from flask import Blueprint

bp = Blueprint("attack", __name__)

from app.blueprints.attack import routes  # noqa: E402,F401
