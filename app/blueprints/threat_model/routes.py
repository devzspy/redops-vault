from flask import redirect, render_template, request, url_for
from flask_jwt_extended import jwt_required

from app.auth_utils import csrf_protect, current_user
from app.blueprints.threat_model import bp
from app.extensions import db
from app.models.engagement import Engagement
from app.models.threat_model import ThreatModel
from app.services import activity_service
from app.services.sanitize_service import clean_html


@bp.route("/engagements/<int:engagement_id>/threat-model")
@jwt_required()
def view_threat_model(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return render_template("threat_model/detail.html", engagement=engagement, plan=engagement.threat_model)


@bp.route("/engagements/<int:engagement_id>/threat-model/edit")
@jwt_required()
def edit_threat_model_form(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return render_template("threat_model/form.html", engagement=engagement, plan=engagement.threat_model)


@bp.route("/engagements/<int:engagement_id>/threat-model/edit", methods=["POST"])
@csrf_protect
def save_threat_model(engagement_id):
    Engagement.query.get_or_404(engagement_id)
    plan = ThreatModel.query.filter_by(engagement_id=engagement_id).first()
    is_new = plan is None
    if is_new:
        plan = ThreatModel(engagement_id=engagement_id)
        db.session.add(plan)

    plan.threat_model = clean_html(request.form.get("threat_model", ""))
    plan.attack_plan = clean_html(request.form.get("attack_plan", ""))
    plan.objectives = clean_html(request.form.get("objectives", ""))
    plan.updated_by_id = int(current_user().id)

    activity_service.log_activity(
        engagement_id,
        "threat_model",
        "created" if is_new else "updated",
        "Recorded the threat model and attack plan" if is_new else "Updated the threat model and attack plan",
    )
    db.session.commit()
    return redirect(url_for("threat_model.view_threat_model", engagement_id=engagement_id))
