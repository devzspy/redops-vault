from flask import render_template
from flask_jwt_extended import jwt_required

from app.auth_utils import current_user
from app.blueprints.scaffolding import bp
from app.models.engagement import Engagement
from app.models.engagement_assignment import EngagementAssignment
from app.models.user import ROLE_BLUETEAM
from app.services.scaffolding_service import build_scaffolding


@bp.route("")
@jwt_required()
def select():
    query = Engagement.query.filter(Engagement.is_archived.is_(False)).order_by(Engagement.name.asc())

    user = current_user()
    if user.role == ROLE_BLUETEAM:
        query = query.join(
            EngagementAssignment, EngagementAssignment.engagement_id == Engagement.id
        ).filter(EngagementAssignment.user_id == user.id)

    return render_template("scaffolding/select.html", engagements=query.all())


@bp.route("/<int:engagement_id>")
@jwt_required()
def generate(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    scaffolding_text = build_scaffolding(engagement)
    return render_template("scaffolding/generate.html", engagement=engagement, scaffolding_text=scaffolding_text)
