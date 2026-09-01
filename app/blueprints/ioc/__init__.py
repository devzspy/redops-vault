from flask import Blueprint

bp = Blueprint("ioc", __name__)

from app.blueprints.ioc import routes  # noqa: E402,F401
