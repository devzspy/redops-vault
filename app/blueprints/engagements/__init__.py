from flask import Blueprint

bp = Blueprint("engagements", __name__, url_prefix="/engagements")

from app.blueprints.engagements import routes  # noqa: E402,F401
