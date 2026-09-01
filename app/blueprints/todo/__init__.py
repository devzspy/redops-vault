from flask import Blueprint

bp = Blueprint("todo", __name__)

from app.blueprints.todo import routes  # noqa: E402,F401
