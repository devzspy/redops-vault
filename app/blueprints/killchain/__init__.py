from flask import Blueprint

bp = Blueprint("killchain", __name__)

from app.blueprints.killchain import routes  # noqa: E402,F401
