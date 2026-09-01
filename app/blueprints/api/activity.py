from flask import Blueprint, jsonify, request

from app.blueprints.api import serializers
from app.models.engagement import Engagement
from app.services import activity_service

bp = Blueprint("api_activity", __name__, url_prefix="/api/v1/engagements/<int:engagement_id>/activity")


@bp.route("", methods=["GET"])
def list_activity(engagement_id):
    Engagement.query.get_or_404(engagement_id)
    limit = request.args.get("limit", activity_service.PER_PAGE, type=int) or activity_service.PER_PAGE
    entries = activity_service.recent_activity(engagement_id, limit=limit)
    return jsonify(activity=[serializers.activity_entry_dict(e) for e in entries])
