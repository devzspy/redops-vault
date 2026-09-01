from flask import render_template
from flask_jwt_extended import jwt_required

from app.blueprints.help import bp


@bp.route("/mcp-server")
@jwt_required()
def mcp_server():
    return render_template("help/mcp_server.html")
