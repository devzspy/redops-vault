from urllib.parse import quote

from flask import Blueprint, Response, abort, jsonify, request, stream_with_context
from werkzeug.utils import secure_filename

from app.auth_utils import current_api_user
from app.blueprints.api import serializers
from app.blueprints.api._common import json_body, pagination_args, str_or_none
from app.extensions import db
from app.models.engagement import Engagement
from app.models.loot import CATEGORIES, LootFile
from app.services import activity_service, loot_service, storage_service

bp = Blueprint("api_loot", __name__, url_prefix="/api/v1/engagements/<int:engagement_id>/loot")


@bp.route("", methods=["GET"])
def list_loot(engagement_id):
    Engagement.query.get_or_404(engagement_id)
    page, per_page = pagination_args()
    pagination = (
        LootFile.query.filter_by(engagement_id=engagement_id)
        .order_by(LootFile.uploaded_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return jsonify(
        files=[serializers.loot_file_dict(f) for f in pagination.items],
        page=pagination.page,
        per_page=per_page,
        total=pagination.total,
        pages=pagination.pages,
    )


@bp.route("", methods=["POST"])
def upload_loot(engagement_id):
    Engagement.query.get_or_404(engagement_id)

    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        abort(400, description="A file is required")

    category = request.form.get("category")
    if category not in CATEGORIES:
        abort(400, description="Invalid category")

    original_filename = secure_filename(uploaded.filename) or "upload.bin"
    field_updates, size, sha256_hex = storage_service.save_upload(uploaded.stream)
    origin = loot_service.resolve_origin_node(
        engagement_id, request.form.get("associated_host", ""), current_api_user().id
    )

    loot_file = LootFile(
        engagement_id=engagement_id,
        original_filename=original_filename,
        category=category,
        description=str_or_none(request.form.get("description")),
        tags=str_or_none(request.form.get("tags")),
        associated_host=origin,
        file_size_bytes=size,
        content_type=uploaded.content_type,
        sha256_plaintext=sha256_hex,
        uploaded_by_id=current_api_user().id,
        **field_updates,
    )
    db.session.add(loot_file)
    db.session.flush()
    activity_service.log_activity(
        engagement_id, "loot_file", "created", f"Uploaded loot file '{loot_file.original_filename}'"
    )
    db.session.commit()
    return jsonify(serializers.loot_file_dict(loot_file)), 201


@bp.route("/<int:file_id>", methods=["GET"])
def get_loot(engagement_id, file_id):
    loot_file = LootFile.query.filter_by(id=file_id, engagement_id=engagement_id).first_or_404()
    return jsonify(serializers.loot_file_dict(loot_file))


@bp.route("/<int:file_id>/download", methods=["GET"])
def download_loot(engagement_id, file_id):
    loot_file = LootFile.query.filter_by(id=file_id, engagement_id=engagement_id).first_or_404()
    generator = storage_service.stream_download(loot_file)
    response = Response(
        stream_with_context(generator), mimetype=loot_file.content_type or "application/octet-stream"
    )
    safe_name = loot_file.original_filename.replace('"', "")
    ascii_name = safe_name.encode("ascii", "ignore").decode("ascii").strip() or "download"
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{ascii_name}"; ' f"filename*=UTF-8''{quote(safe_name)}"
    )
    if loot_file.sha256_plaintext:
        response.headers["X-Sha256"] = loot_file.sha256_plaintext
    return response


@bp.route("/<int:file_id>", methods=["PATCH"])
def update_loot(engagement_id, file_id):
    loot_file = LootFile.query.filter_by(id=file_id, engagement_id=engagement_id).first_or_404()
    data = json_body()

    if "category" in data:
        if data["category"] not in CATEGORIES:
            abort(400, description="Invalid category")
        loot_file.category = data["category"]
    if "description" in data:
        loot_file.description = str_or_none(data.get("description"))
    if "tags" in data:
        loot_file.tags = str_or_none(data.get("tags"))
    if "associated_host" in data:
        loot_file.associated_host = loot_service.resolve_origin_node(
            engagement_id, data.get("associated_host") or "", current_api_user().id
        )

    activity_service.log_activity(
        engagement_id, "loot_file", "updated", f"Updated loot file '{loot_file.original_filename}'"
    )
    db.session.commit()
    return jsonify(serializers.loot_file_dict(loot_file))


@bp.route("/<int:file_id>", methods=["DELETE"])
def delete_loot(engagement_id, file_id):
    loot_file = LootFile.query.filter_by(id=file_id, engagement_id=engagement_id).first_or_404()
    activity_service.log_activity(
        engagement_id, "loot_file", "deleted", f"Deleted loot file '{loot_file.original_filename}'"
    )
    db.session.delete(loot_file)
    db.session.commit()
    return "", 204
