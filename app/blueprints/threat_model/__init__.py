from flask import Blueprint

bp = Blueprint("threat_model", __name__)

from app.blueprints.threat_model import routes  # noqa: E402,F401
