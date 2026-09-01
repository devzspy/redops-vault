from flask import Blueprint, abort, jsonify, request

from app.auth_utils import current_api_user
from app.blueprints.api import serializers
from app.blueprints.api._common import json_body
from app.extensions import db
from app.models.engagement import Engagement
from app.models.loot import Credential
from app.services import activity_service, credential_service

bp = Blueprint(
    "api_credentials", __name__, url_prefix="/api/v1/engagements/<int:engagement_id>/credentials"
)


@bp.route("", methods=["GET"])
def list_credentials(engagement_id):
    Engagement.query.get_or_404(engagement_id)
    creds = Credential.query.filter_by(engagement_id=engagement_id).order_by(Credential.added_at.desc()).all()
    return jsonify(credentials=[serializers.credential_dict(c) for c in creds])


@bp.route("", methods=["POST"])
def create_credential(engagement_id):
    Engagement.query.get_or_404(engagement_id)
    data = json_body()

    credential = Credential(engagement_id=engagement_id, added_by_id=current_api_user().id)
    try:
        error = credential_service.apply_fields(credential, data)
    except ValueError as exc:
        abort(400, description=str(exc))
    if error is not None:
        abort(400, description=error)

    db.session.add(credential)
    db.session.flush()
    activity_service.log_activity(
        engagement_id, "credential", "created", f"Added credential '{credential.username or '(no username)'}'"
    )
    db.session.commit()
    return jsonify(serializers.credential_dict(credential, reveal=True)), 201


@bp.route("/<int:cred_id>", methods=["GET"])
def get_credential(engagement_id, cred_id):
    credential = Credential.query.filter_by(id=cred_id, engagement_id=engagement_id).first_or_404()
    reveal = request.args.get("reveal") == "true"
    return jsonify(serializers.credential_dict(credential, reveal=reveal))


@bp.route("/<int:cred_id>", methods=["PATCH"])
def update_credential(engagement_id, cred_id):
    credential = Credential.query.filter_by(id=cred_id, engagement_id=engagement_id).first_or_404()
    data = json_body()

    try:
        error = credential_service.apply_fields(credential, data)
    except ValueError as exc:
        abort(400, description=str(exc))
    if error is not None:
        abort(400, description=error)

    activity_service.log_activity(
        engagement_id, "credential", "updated", f"Updated credential '{credential.username or '(no username)'}'"
    )
    db.session.commit()
    return jsonify(serializers.credential_dict(credential, reveal=True))


@bp.route("/<int:cred_id>", methods=["DELETE"])
def delete_credential(engagement_id, cred_id):
    credential = Credential.query.filter_by(id=cred_id, engagement_id=engagement_id).first_or_404()
    activity_service.log_activity(
        engagement_id, "credential", "deleted", f"Deleted credential '{credential.username or '(no username)'}'"
    )
    db.session.delete(credential)
    db.session.commit()
    return "", 204


@bp.route("/<int:cred_id>/totp", methods=["GET"])
def credential_totp_code(engagement_id, cred_id):
    credential = Credential.query.filter_by(id=cred_id, engagement_id=engagement_id).first_or_404()
    status = credential_service.totp_status(credential)
    if status is None:
        abort(404)
    return jsonify(status)
