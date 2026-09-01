from flask import Blueprint, jsonify

from app.auth_utils import current_api_user
from app.blueprints.api import serializers
from app.blueprints.api._common import json_body
from app.extensions import db
from app.models.engagement import Engagement
from app.models.threat_model import ThreatModel
from app.services import activity_service
from app.services.sanitize_service import clean_html

bp = Blueprint(
    "api_threat_model", __name__, url_prefix="/api/v1/engagements/<int:engagement_id>/threat-model"
)


@bp.route("", methods=["GET"])
def get_threat_model(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return jsonify(threat_model=serializers.threat_model_dict(engagement.threat_model))


@bp.route("", methods=["PUT"])
def save_threat_model(engagement_id):
    Engagement.query.get_or_404(engagement_id)
    plan = ThreatModel.query.filter_by(engagement_id=engagement_id).first()
    is_new = plan is None
    if is_new:
        plan = ThreatModel(engagement_id=engagement_id)
        db.session.add(plan)

    data = json_body()
    plan.threat_model = clean_html(data.get("threat_model", ""))
    plan.attack_plan = clean_html(data.get("attack_plan", ""))
    plan.objectives = clean_html(data.get("objectives", ""))
    plan.updated_by_id = current_api_user().id

    activity_service.log_activity(
        engagement_id,
        "threat_model",
        "created" if is_new else "updated",
        "Recorded the threat model and attack plan" if is_new else "Updated the threat model and attack plan",
    )
    db.session.commit()
    return jsonify(threat_model=serializers.threat_model_dict(plan))
