from flask import Blueprint

bp = Blueprint("scaffolding", __name__, url_prefix="/scaffolding")

from app.blueprints.scaffolding import routes  # noqa: E402,F401
