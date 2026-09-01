from urllib.parse import quote

from flask import (
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    stream_with_context,
    url_for,
)
from flask_jwt_extended import jwt_required
from werkzeug.utils import secure_filename

from app.auth_utils import csrf_protect, current_user
from app.blueprints.loot import bp
from app.extensions import db
from app.models.engagement import Engagement
from app.models.infrastructure import TARGET_ROLES, InfrastructureNode
from app.models.loot import CATEGORIES, CREDENTIAL_STATUSES, CREDENTIAL_TYPES, Credential, LootFile
from app.services import activity_service, credential_service, loot_service, storage_service

PER_PAGE = 20
OTHER_HOST_VALUE = "__other__"


@bp.route("/engagements/<int:engagement_id>/loot")
@jwt_required()
def list_loot(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    page = request.args.get("page", 1, type=int)
    pagination = (
        LootFile.query.filter_by(engagement_id=engagement_id)
        .order_by(LootFile.uploaded_at.desc())
        .paginate(page=page, per_page=PER_PAGE, error_out=False)
    )
    return render_template(
        "loot/list.html", engagement=engagement, files=pagination.items, pagination=pagination
    )


@bp.route("/engagements/<int:engagement_id>/loot/upload")
@jwt_required()
def upload_form(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return render_template(
        "loot/upload_form.html",
        engagement=engagement,
        categories=CATEGORIES,
        nodes=_target_infrastructure_nodes(engagement_id),
    )


@bp.route("/engagements/<int:engagement_id>/loot/upload", methods=["POST"])
@csrf_protect
def upload_loot(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)

    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        flash("Please choose a file to upload.", "danger")
        return redirect(url_for("loot.upload_form", engagement_id=engagement_id))

    category = request.form.get("category")
    if category not in CATEGORIES:
        abort(400, description="Invalid category")

    original_filename = secure_filename(uploaded.filename) or "upload.bin"
    field_updates, size, sha256_hex = storage_service.save_upload(uploaded.stream)
    origin = loot_service.resolve_origin_node(engagement_id, _submitted_origin(), int(current_user().id))

    loot_file = LootFile(
        engagement_id=engagement_id,
        original_filename=original_filename,
        category=category,
        description=request.form.get("description", "").strip() or None,
        tags=request.form.get("tags", "").strip() or None,
        associated_host=origin,
        file_size_bytes=size,
        content_type=uploaded.content_type,
        sha256_plaintext=sha256_hex,
        uploaded_by_id=int(current_user().id),
        **field_updates,
    )
    db.session.add(loot_file)
    db.session.flush()
    activity_service.log_activity(
        engagement_id, "loot_file", "created", f"Uploaded loot file '{loot_file.original_filename}'"
    )
    db.session.commit()
    flash("File uploaded and encrypted at rest.", "success")
    return redirect(url_for("loot.file_detail", engagement_id=engagement_id, file_id=loot_file.id))


@bp.route("/engagements/<int:engagement_id>/loot/<int:file_id>")
@jwt_required()
def file_detail(engagement_id, file_id):
    from app.models.attack import AttackTechnique

    loot_file = LootFile.query.filter_by(id=file_id, engagement_id=engagement_id).first_or_404()
    techniques = AttackTechnique.query.order_by(AttackTechnique.attack_id.asc()).all()
    return render_template(
        "loot/file_detail.html",
        engagement=loot_file.engagement,
        file=loot_file,
        techniques=techniques,
        nodes=_target_infrastructure_nodes(engagement_id),
    )


@bp.route("/engagements/<int:engagement_id>/loot/<int:file_id>/download")
@jwt_required()
def download_loot(engagement_id, file_id):
    loot_file = LootFile.query.filter_by(id=file_id, engagement_id=engagement_id).first_or_404()

    generator = storage_service.stream_download(loot_file)
    response = Response(
        stream_with_context(generator),
        mimetype=loot_file.content_type or "application/octet-stream",
    )
    safe_name = loot_file.original_filename.replace('"', "")
    ascii_name = safe_name.encode("ascii", "ignore").decode("ascii").strip() or "download"
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{ascii_name}"; ' f"filename*=UTF-8''{quote(safe_name)}"
    )
    return response


@bp.route("/engagements/<int:engagement_id>/loot/<int:file_id>/edit", methods=["POST"])
@csrf_protect
def edit_loot(engagement_id, file_id):
    loot_file = LootFile.query.filter_by(id=file_id, engagement_id=engagement_id).first_or_404()

    category = request.form.get("category")
    if category not in CATEGORIES:
        abort(400, description="Invalid category")

    loot_file.category = category
    loot_file.description = request.form.get("description", "").strip() or None
    loot_file.tags = request.form.get("tags", "").strip() or None
    loot_file.associated_host = loot_service.resolve_origin_node(
        engagement_id, _submitted_origin(), int(current_user().id)
    )
    activity_service.log_activity(
        engagement_id, "loot_file", "updated", f"Updated loot file '{loot_file.original_filename}'"
    )
    db.session.commit()
    flash("Loot metadata updated.", "success")
    return redirect(url_for("loot.file_detail", engagement_id=engagement_id, file_id=file_id))


@bp.route("/engagements/<int:engagement_id>/loot/<int:file_id>/delete", methods=["POST"])
@csrf_protect
def delete_loot(engagement_id, file_id):
    loot_file = LootFile.query.filter_by(id=file_id, engagement_id=engagement_id).first_or_404()
    activity_service.log_activity(
        engagement_id, "loot_file", "deleted", f"Deleted loot file '{loot_file.original_filename}'"
    )
    db.session.delete(loot_file)
    db.session.commit()
    flash("Loot file deleted.", "success")
    return redirect(url_for("loot.list_loot", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/credentials")
@jwt_required()
def list_credentials(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    creds = (
        Credential.query.filter_by(engagement_id=engagement_id)
        .order_by(Credential.added_at.desc())
        .all()
    )
    decrypted = [_credential_row(c) for c in creds]
    return render_template("loot/credential_list.html", engagement=engagement, rows=decrypted)


def _credential_row(c):
    decrypted = credential_service.decrypt(c)
    status = credential_service.totp_status(c)
    decrypted.pop("totp_secret")
    decrypted["credential"] = c
    decrypted["has_totp"] = status is not None
    decrypted["totp_code"] = status["code"] if status else None
    decrypted["totp_seconds_remaining"] = status["seconds_remaining"] if status else None
    return decrypted


def _target_infrastructure_nodes(engagement_id):
    return (
        InfrastructureNode.query.filter_by(engagement_id=engagement_id)
        .filter(InfrastructureNode.role.in_(TARGET_ROLES))
        .order_by(InfrastructureNode.name.asc())
        .all()
    )


def _submitted_origin():
    selected = request.form.get("associated_host", "").strip()
    if selected == OTHER_HOST_VALUE:
        return request.form.get("associated_host_other", "").strip()
    return selected


def _apply_credential_form(credential, engagement_id):
    """Validates and applies the submitted credential form fields onto
    `credential`. Returns an error redirect response if validation fails,
    or None on success.
    """
    try:
        error = credential_service.apply_fields(credential, request.form)
    except ValueError as exc:
        abort(400, description=str(exc))
    if error is None:
        return None

    flash(error, "danger")
    if credential.id:
        redirect_target = url_for("loot.edit_credential_form", engagement_id=engagement_id, cred_id=credential.id)
    else:
        redirect_target = url_for("loot.new_credential_form", engagement_id=engagement_id)
    return redirect(redirect_target)


@bp.route("/engagements/<int:engagement_id>/credentials/new")
@jwt_required()
def new_credential_form(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return render_template(
        "loot/credential_form.html",
        engagement=engagement,
        credential=None,
        decrypted=credential_service.empty_decrypted(),
        credential_types=CREDENTIAL_TYPES,
        statuses=CREDENTIAL_STATUSES,
        nodes=_target_infrastructure_nodes(engagement_id),
    )


@bp.route("/engagements/<int:engagement_id>/credentials", methods=["POST"])
@csrf_protect
def create_credential(engagement_id):
    Engagement.query.get_or_404(engagement_id)

    credential = Credential(engagement_id=engagement_id, added_by_id=int(current_user().id))
    error_response = _apply_credential_form(credential, engagement_id)
    if error_response is not None:
        return error_response

    db.session.add(credential)
    db.session.flush()
    activity_service.log_activity(
        engagement_id,
        "credential",
        "created",
        f"Added credential '{credential.username or '(no username)'}'",
    )
    db.session.commit()
    flash("Credential added.", "success")
    return redirect(url_for("loot.list_credentials", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/credentials/<int:cred_id>/edit")
@jwt_required()
def edit_credential_form(engagement_id, cred_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    credential = Credential.query.filter_by(id=cred_id, engagement_id=engagement_id).first_or_404()
    return render_template(
        "loot/credential_form.html",
        engagement=engagement,
        credential=credential,
        decrypted=credential_service.decrypt(credential),
        credential_types=CREDENTIAL_TYPES,
        statuses=CREDENTIAL_STATUSES,
        nodes=_target_infrastructure_nodes(engagement_id),
    )


@bp.route("/engagements/<int:engagement_id>/credentials/<int:cred_id>/edit", methods=["POST"])
@csrf_protect
def edit_credential(engagement_id, cred_id):
    credential = Credential.query.filter_by(id=cred_id, engagement_id=engagement_id).first_or_404()

    error_response = _apply_credential_form(credential, engagement_id)
    if error_response is not None:
        return error_response

    activity_service.log_activity(
        engagement_id,
        "credential",
        "updated",
        f"Updated credential '{credential.username or '(no username)'}'",
    )
    db.session.commit()
    flash("Credential updated.", "success")
    return redirect(url_for("loot.list_credentials", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/credentials/<int:cred_id>/totp")
@jwt_required()
def credential_totp_code(engagement_id, cred_id):
    credential = Credential.query.filter_by(id=cred_id, engagement_id=engagement_id).first_or_404()
    status = credential_service.totp_status(credential)
    if status is None:
        abort(404)
    return jsonify(code=status["code"], seconds_remaining=status["seconds_remaining"])


@bp.route("/engagements/<int:engagement_id>/credentials/<int:cred_id>/delete", methods=["POST"])
@csrf_protect
def delete_credential(engagement_id, cred_id):
    credential = Credential.query.filter_by(id=cred_id, engagement_id=engagement_id).first_or_404()
    activity_service.log_activity(
        engagement_id,
        "credential",
        "deleted",
        f"Deleted credential '{credential.username or '(no username)'}'",
    )
    db.session.delete(credential)
    db.session.commit()
    flash("Credential deleted.", "success")
    return redirect(url_for("loot.list_credentials", engagement_id=engagement_id))
