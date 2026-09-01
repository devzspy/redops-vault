from flask import Blueprint, abort, jsonify

from app.auth_utils import current_api_user
from app.blueprints.api import serializers
from app.blueprints.api._common import json_body, parse_datetime, str_or_none
from app.extensions import db
from app.models.engagement import Engagement
from app.models.ioc import HASH_TYPES, IOC
from app.services import activity_service

bp = Blueprint("api_ioc", __name__, url_prefix="/api/v1/engagements/<int:engagement_id>/iocs")


@bp.route("", methods=["GET"])
def list_iocs(engagement_id):
    Engagement.query.get_or_404(engagement_id)
    iocs = (
        IOC.query.filter_by(engagement_id=engagement_id)
        .order_by(IOC.dropped_at.desc().nullslast(), IOC.added_at.desc())
        .all()
    )
    return jsonify(iocs=[serializers.ioc_dict(i) for i in iocs])


@bp.route("", methods=["POST"])
def create_ioc(engagement_id):
    Engagement.query.get_or_404(engagement_id)
    data = json_body()
    hash_type = data.get("hash_type") or None
    if hash_type and hash_type not in HASH_TYPES:
        abort(400, description="Invalid hash type")

    ioc = IOC(
        engagement_id=engagement_id,
        host=str_or_none(data.get("host")),
        location=str_or_none(data.get("location")),
        hash_type=hash_type,
        hash_value=str_or_none(data.get("hash_value")),
        dropped_at=parse_datetime(data.get("dropped_at")),
        notes=str_or_none(data.get("notes")),
        added_by_id=current_api_user().id,
    )
    db.session.add(ioc)
    db.session.flush()
    activity_service.log_activity(engagement_id, "ioc", "created", f"Added IOC '{ioc.display_label()}'")
    db.session.commit()
    return jsonify(serializers.ioc_dict(ioc)), 201


@bp.route("/<int:ioc_id>", methods=["GET"])
def get_ioc(engagement_id, ioc_id):
    ioc = IOC.query.filter_by(id=ioc_id, engagement_id=engagement_id).first_or_404()
    return jsonify(serializers.ioc_dict(ioc))


@bp.route("/<int:ioc_id>", methods=["PATCH"])
def update_ioc(engagement_id, ioc_id):
    ioc = IOC.query.filter_by(id=ioc_id, engagement_id=engagement_id).first_or_404()
    data = json_body()

    if "host" in data:
        ioc.host = str_or_none(data.get("host"))
    if "location" in data:
        ioc.location = str_or_none(data.get("location"))
    if "hash_type" in data:
        hash_type = data.get("hash_type") or None
        if hash_type and hash_type not in HASH_TYPES:
            abort(400, description="Invalid hash type")
        ioc.hash_type = hash_type
    if "hash_value" in data:
        ioc.hash_value = str_or_none(data.get("hash_value"))
    if "dropped_at" in data:
        ioc.dropped_at = parse_datetime(data.get("dropped_at"))
    if "notes" in data:
        ioc.notes = str_or_none(data.get("notes"))

    activity_service.log_activity(engagement_id, "ioc", "updated", f"Updated IOC '{ioc.display_label()}'")
    db.session.commit()
    return jsonify(serializers.ioc_dict(ioc))


@bp.route("/<int:ioc_id>", methods=["DELETE"])
def delete_ioc(engagement_id, ioc_id):
    ioc = IOC.query.filter_by(id=ioc_id, engagement_id=engagement_id).first_or_404()
    activity_service.log_activity(engagement_id, "ioc", "deleted", f"Deleted IOC '{ioc.display_label()}'")
    db.session.delete(ioc)
    db.session.commit()
    return "", 204
