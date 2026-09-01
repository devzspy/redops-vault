from flask import Blueprint, abort, jsonify, request

from app.auth_utils import current_api_user
from app.blueprints.api import serializers
from app.blueprints.api._common import json_body, parse_date, require_choice, require_fields, str_or_none
from app.extensions import db
from app.models.engagement import STATUS_LABELS, STATUSES, Engagement
from app.models.engagement_assignment import EngagementAssignment
from app.models.engagement_link import LINK_TYPE_EXTERNAL, LINK_TYPES, EngagementLink
from app.models.killchain import KILL_CHAIN_MODEL_LMCKC, KILL_CHAIN_MODELS, KillChainEntry
from app.models.user import ROLE_BLUETEAM
from app.services import activity_service

bp = Blueprint("api_engagements", __name__, url_prefix="/api/v1/engagements")


@bp.route("", methods=["GET"])
def list_engagements():
    show_archived = request.args.get("show_archived") == "1"
    query = Engagement.query.order_by(Engagement.created_at.desc())
    if not show_archived:
        query = query.filter(Engagement.is_archived.is_(False))

    user = current_api_user()
    if user.role == ROLE_BLUETEAM:
        query = query.join(
            EngagementAssignment, EngagementAssignment.engagement_id == Engagement.id
        ).filter(EngagementAssignment.user_id == user.id)

    return jsonify(engagements=[serializers.engagement_summary_dict(e) for e in query.all()])


@bp.route("", methods=["POST"])
def create_engagement():
    data = json_body()
    require_fields(data, "name", "client_name")

    kill_chain_model = data.get("kill_chain_model") or KILL_CHAIN_MODEL_LMCKC
    require_choice(kill_chain_model, KILL_CHAIN_MODELS, "kill_chain_model")

    engagement = Engagement(
        name=data["name"].strip(),
        client_name=data["client_name"].strip(),
        description=str_or_none(data.get("description")),
        start_date=parse_date(data.get("start_date")),
        end_date=parse_date(data.get("end_date")),
        kill_chain_model=kill_chain_model,
        created_by_id=current_api_user().id,
    )
    db.session.add(engagement)
    db.session.flush()
    activity_service.log_activity(engagement.id, "engagement", "created", f"Created engagement '{engagement.name}'")
    db.session.commit()
    return jsonify(serializers.engagement_detail_dict(engagement)), 201


@bp.route("/<int:engagement_id>", methods=["GET"])
def get_engagement(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return jsonify(serializers.engagement_detail_dict(engagement))


@bp.route("/<int:engagement_id>", methods=["PATCH"])
def update_engagement(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    data = json_body()

    if "name" in data:
        name = str_or_none(data.get("name"))
        if not name:
            abort(400, description="name cannot be blank")
        engagement.name = name
    if "client_name" in data:
        client_name = str_or_none(data.get("client_name"))
        if not client_name:
            abort(400, description="client_name cannot be blank")
        engagement.client_name = client_name
    if "description" in data:
        engagement.description = str_or_none(data.get("description"))
    if "start_date" in data:
        engagement.start_date = parse_date(data.get("start_date"))
    if "end_date" in data:
        engagement.end_date = parse_date(data.get("end_date"))
    if "kill_chain_model" in data:
        if KillChainEntry.query.filter_by(engagement_id=engagement.id).first() is not None:
            abort(400, description="kill_chain_model cannot be changed once the engagement has kill chain entries")
        require_choice(data.get("kill_chain_model"), KILL_CHAIN_MODELS, "kill_chain_model")
        engagement.kill_chain_model = data["kill_chain_model"]

    activity_service.log_activity(engagement.id, "engagement", "updated", "Updated engagement details")
    db.session.commit()
    return jsonify(serializers.engagement_detail_dict(engagement))


@bp.route("/<int:engagement_id>/status", methods=["POST"])
def change_status(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    status = json_body().get("status")
    require_choice(status, STATUSES, "status")

    engagement.status = status
    activity_service.log_activity(
        engagement.id, "engagement", "status_changed", f"Changed status to {STATUS_LABELS.get(status, status)}"
    )
    db.session.commit()
    return jsonify(serializers.engagement_detail_dict(engagement))


@bp.route("/<int:engagement_id>/archive", methods=["POST"])
def toggle_archive(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    engagement.is_archived = not engagement.is_archived
    activity_service.log_activity(
        engagement.id,
        "engagement",
        "archived" if engagement.is_archived else "restored",
        "Archived engagement" if engagement.is_archived else "Restored engagement from archive",
    )
    db.session.commit()
    return jsonify(serializers.engagement_detail_dict(engagement))


@bp.route("/<int:engagement_id>/links", methods=["GET"])
def list_links(engagement_id):
    Engagement.query.get_or_404(engagement_id)
    links = (
        EngagementLink.query.filter_by(engagement_id=engagement_id)
        .order_by(EngagementLink.added_at.desc())
        .all()
    )
    return jsonify(links=[serializers.engagement_link_dict(link) for link in links])


@bp.route("/<int:engagement_id>/links", methods=["POST"])
def create_link(engagement_id):
    Engagement.query.get_or_404(engagement_id)
    data = json_body()
    require_fields(data, "url")
    link_type = data.get("link_type", LINK_TYPE_EXTERNAL)
    require_choice(link_type, LINK_TYPES, "link_type")

    link = EngagementLink(
        engagement_id=engagement_id,
        link_type=link_type,
        url=data["url"].strip(),
        label=str_or_none(data.get("label")),
        notes=str_or_none(data.get("notes")),
        added_by_id=current_api_user().id,
    )
    db.session.add(link)
    db.session.flush()
    activity_service.log_activity(
        engagement_id, "link", "created", f"Added {link.link_type_label().lower()} link '{link.display_label()}'"
    )
    db.session.commit()
    return jsonify(serializers.engagement_link_dict(link)), 201


@bp.route("/<int:engagement_id>/links/<int:link_id>", methods=["PATCH"])
def update_link(engagement_id, link_id):
    link = EngagementLink.query.filter_by(id=link_id, engagement_id=engagement_id).first_or_404()
    data = json_body()

    if "url" in data:
        url = str_or_none(data.get("url"))
        if not url:
            abort(400, description="url cannot be blank")
        link.url = url
    if "link_type" in data:
        require_choice(data.get("link_type"), LINK_TYPES, "link_type")
        link.link_type = data["link_type"]
    if "label" in data:
        link.label = str_or_none(data.get("label"))
    if "notes" in data:
        link.notes = str_or_none(data.get("notes"))

    activity_service.log_activity(
        engagement_id, "link", "updated", f"Updated {link.link_type_label().lower()} link '{link.display_label()}'"
    )
    db.session.commit()
    return jsonify(serializers.engagement_link_dict(link))


@bp.route("/<int:engagement_id>/links/<int:link_id>", methods=["DELETE"])
def delete_link(engagement_id, link_id):
    link = EngagementLink.query.filter_by(id=link_id, engagement_id=engagement_id).first_or_404()
    activity_service.log_activity(
        engagement_id, "link", "deleted", f"Deleted {link.link_type_label().lower()} link '{link.display_label()}'"
    )
    db.session.delete(link)
    db.session.commit()
    return "", 204
