from datetime import datetime

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import jwt_required

from app.auth_utils import csrf_protect, current_user, role_required_csrf
from app.blueprints.engagements import bp
from app.extensions import db
from app.models.app_setting import INFRA_ENGAGEMENT, AppSetting
from app.models.engagement import STATUS_LABELS, STATUSES, Engagement
from app.models.engagement_assignment import EngagementAssignment
from app.models.engagement_deletion_request import EngagementDeletionRequest
from app.models.engagement_link import LINK_TYPES, LINK_TYPE_EXTERNAL, EngagementLink
from app.models.killchain import KILL_CHAIN_MODEL_LABELS, KILL_CHAIN_MODEL_LMCKC, KILL_CHAIN_MODELS
from app.models.todo import STATUS_DONE, Todo
from app.models.user import ROLE_ADMIN, ROLE_BLUETEAM, ROLE_OPERATOR
from app.services import activity_service


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@bp.route("")
@jwt_required()
def list_engagements():
    setting = AppSetting.get()
    if setting.infra_mode == INFRA_ENGAGEMENT and setting.engagement_id:
        return redirect(url_for("engagements.engagement_detail", engagement_id=setting.engagement_id))

    show_archived = request.args.get("show_archived") == "1"

    query = Engagement.query.order_by(Engagement.created_at.desc())
    if not show_archived:
        query = query.filter(Engagement.is_archived.is_(False))

    user = current_user()
    if user.role == ROLE_BLUETEAM:
        query = query.join(
            EngagementAssignment, EngagementAssignment.engagement_id == Engagement.id
        ).filter(EngagementAssignment.user_id == user.id)

    engagements_by_status = {status: [] for status in STATUSES}
    for engagement in query.all():
        engagements_by_status.setdefault(engagement.status, []).append(engagement)

    return render_template(
        "engagements/list.html",
        engagements_by_status=engagements_by_status,
        statuses=STATUSES,
        status_labels=STATUS_LABELS,
        show_archived=show_archived,
    )


@bp.route("/new")
@jwt_required()
def new_engagement_form():
    return render_template(
        "engagements/form.html",
        engagement=None,
        statuses=STATUSES,
        kill_chain_models=KILL_CHAIN_MODELS,
        kill_chain_model_labels=KILL_CHAIN_MODEL_LABELS,
        default_kill_chain_model=AppSetting.get().default_kill_chain_model,
    )


@bp.route("", methods=["POST"])
@csrf_protect
def create_engagement():
    name = request.form.get("name", "").strip()
    client_name = request.form.get("client_name", "").strip()
    if not name or not client_name:
        flash("Name and client name are required.", "danger")
        return redirect(url_for("engagements.new_engagement_form"))

    kill_chain_model = request.form.get("kill_chain_model") or KILL_CHAIN_MODEL_LMCKC
    if kill_chain_model not in KILL_CHAIN_MODELS:
        abort(400, description="Invalid kill chain model")

    engagement = Engagement(
        name=name,
        client_name=client_name,
        description=request.form.get("description", "").strip() or None,
        start_date=_parse_date(request.form.get("start_date")),
        end_date=_parse_date(request.form.get("end_date")),
        kill_chain_model=kill_chain_model,
        created_by_id=int(current_user().id),
    )
    db.session.add(engagement)
    db.session.flush()
    activity_service.log_activity(
        engagement.id, "engagement", "created", f"Created engagement '{engagement.name}'"
    )
    db.session.commit()
    flash("Engagement created.", "success")
    return redirect(url_for("engagements.engagement_detail", engagement_id=engagement.id))


@bp.route("/<int:engagement_id>")
@jwt_required()
def engagement_detail(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)

    all_todos = (
        Todo.query.filter_by(engagement_id=engagement_id).order_by(Todo.created_at.asc()).all()
    )
    in_progress_todos = [t for t in all_todos if t.is_in_progress()]
    available_todos = [t for t in all_todos if t.is_available()]
    done_todos = sorted(
        (t for t in all_todos if t.status == STATUS_DONE),
        key=lambda t: t.completed_at or t.updated_at,
        reverse=True,
    )

    links = (
        EngagementLink.query.filter_by(engagement_id=engagement_id)
        .order_by(EngagementLink.added_at.desc())
        .all()
    )

    return render_template(
        "engagements/detail.html",
        engagement=engagement,
        statuses=STATUSES,
        status_labels=STATUS_LABELS,
        kill_chain_model_labels=KILL_CHAIN_MODEL_LABELS,
        activity_entries=activity_service.recent_activity(engagement_id),
        in_progress_todos=in_progress_todos,
        available_todos=available_todos,
        done_todos=done_todos,
        links=links,
        link_types=LINK_TYPES,
        deletion_request=engagement.deletion_request,
    )


@bp.route("/<int:engagement_id>/edit")
@jwt_required()
def edit_engagement_form(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return render_template(
        "engagements/form.html",
        engagement=engagement,
        statuses=STATUSES,
        kill_chain_models=KILL_CHAIN_MODELS,
        kill_chain_model_labels=KILL_CHAIN_MODEL_LABELS,
    )


@bp.route("/<int:engagement_id>/edit", methods=["POST"])
@csrf_protect
def edit_engagement(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    name = request.form.get("name", "").strip()
    client_name = request.form.get("client_name", "").strip()
    if not name or not client_name:
        flash("Name and client name are required.", "danger")
        return redirect(url_for("engagements.edit_engagement_form", engagement_id=engagement_id))

    engagement.name = name
    engagement.client_name = client_name
    engagement.description = request.form.get("description", "").strip() or None
    engagement.start_date = _parse_date(request.form.get("start_date"))
    engagement.end_date = _parse_date(request.form.get("end_date"))
    if not engagement.killchain_entries:
        kill_chain_model = request.form.get("kill_chain_model") or KILL_CHAIN_MODEL_LMCKC
        if kill_chain_model not in KILL_CHAIN_MODELS:
            abort(400, description="Invalid kill chain model")
        engagement.kill_chain_model = kill_chain_model
    activity_service.log_activity(engagement.id, "engagement", "updated", "Updated engagement details")
    db.session.commit()
    flash("Engagement updated.", "success")
    return redirect(url_for("engagements.engagement_detail", engagement_id=engagement.id))


@bp.route("/<int:engagement_id>/status", methods=["POST"])
@csrf_protect
def change_status(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    status = request.form.get("status")
    if status not in STATUSES:
        abort(400, description="Invalid status")
    engagement.status = status
    activity_service.log_activity(
        engagement.id,
        "engagement",
        "status_changed",
        f"Changed status to {STATUS_LABELS.get(status, status)}",
    )
    db.session.commit()

    if request.form.get("ajax") == "1":
        return jsonify({"ok": True, "status": status})

    flash(f"Engagement status set to {STATUS_LABELS.get(status, status)}.", "success")
    return redirect(url_for("engagements.engagement_detail", engagement_id=engagement.id))


@bp.route("/<int:engagement_id>/archive", methods=["POST"])
@csrf_protect
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
    flash(
        "Engagement archived." if engagement.is_archived else "Engagement restored from archive.",
        "success",
    )
    return redirect(url_for("engagements.engagement_detail", engagement_id=engagement.id))


@bp.route("/<int:engagement_id>/links", methods=["POST"])
@csrf_protect
def create_link(engagement_id):
    Engagement.query.get_or_404(engagement_id)

    url = request.form.get("url", "").strip()
    if not url:
        flash("URL is required.", "danger")
        return redirect(url_for("engagements.engagement_detail", engagement_id=engagement_id))

    link_type = request.form.get("link_type", LINK_TYPE_EXTERNAL)
    if link_type not in LINK_TYPES:
        abort(400, description="Invalid link type")

    link = EngagementLink(
        engagement_id=engagement_id,
        link_type=link_type,
        url=url,
        label=request.form.get("label", "").strip() or None,
        notes=request.form.get("notes", "").strip() or None,
        added_by_id=int(current_user().id),
    )
    db.session.add(link)
    db.session.flush()
    activity_service.log_activity(
        engagement_id, "link", "created", f"Added {link.link_type_label().lower()} link '{link.display_label()}'"
    )
    db.session.commit()
    flash("Link added.", "success")
    return redirect(url_for("engagements.engagement_detail", engagement_id=engagement_id))


@bp.route("/<int:engagement_id>/links/<int:link_id>/edit", methods=["POST"])
@csrf_protect
def update_link(engagement_id, link_id):
    link = EngagementLink.query.filter_by(id=link_id, engagement_id=engagement_id).first_or_404()

    url = request.form.get("url", "").strip()
    if not url:
        flash("URL is required.", "danger")
        return redirect(url_for("engagements.engagement_detail", engagement_id=engagement_id))

    link_type = request.form.get("link_type", LINK_TYPE_EXTERNAL)
    if link_type not in LINK_TYPES:
        abort(400, description="Invalid link type")

    link.link_type = link_type
    link.url = url
    link.label = request.form.get("label", "").strip() or None
    link.notes = request.form.get("notes", "").strip() or None
    activity_service.log_activity(
        engagement_id, "link", "updated", f"Updated {link.link_type_label().lower()} link '{link.display_label()}'"
    )
    db.session.commit()
    flash("Link updated.", "success")
    return redirect(url_for("engagements.engagement_detail", engagement_id=engagement_id))


@bp.route("/<int:engagement_id>/links/<int:link_id>/delete", methods=["POST"])
@csrf_protect
def delete_link(engagement_id, link_id):
    link = EngagementLink.query.filter_by(id=link_id, engagement_id=engagement_id).first_or_404()
    activity_service.log_activity(
        engagement_id, "link", "deleted", f"Deleted {link.link_type_label().lower()} link '{link.display_label()}'"
    )
    db.session.delete(link)
    db.session.commit()
    flash("Link deleted.", "success")
    return redirect(url_for("engagements.engagement_detail", engagement_id=engagement_id))


@bp.route("/<int:engagement_id>/delete/request", methods=["POST"])
@role_required_csrf("admin")
def request_engagement_deletion(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    if engagement.deletion_request is not None:
        flash("A deletion request is already pending for this engagement.", "warning")
        return redirect(url_for("engagements.engagement_detail", engagement_id=engagement_id))

    requested_by = current_user()
    db.session.add(
        EngagementDeletionRequest(engagement_id=engagement_id, requested_by_id=requested_by.id)
    )
    activity_service.log_activity(
        engagement_id,
        "engagement",
        "deletion_requested",
        f"Requested deletion of engagement '{engagement.name}' "
        "(requires approval from another admin or operator)",
    )
    db.session.commit()
    flash(
        "Deletion requested. It needs approval from another admin or operator before it takes effect.",
        "warning",
    )
    return redirect(url_for("engagements.engagement_detail", engagement_id=engagement_id))


@bp.route("/<int:engagement_id>/delete/cancel", methods=["POST"])
@role_required_csrf("admin")
def cancel_engagement_deletion(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    if engagement.deletion_request is None:
        flash("There is no pending deletion request for this engagement.", "warning")
        return redirect(url_for("engagements.engagement_detail", engagement_id=engagement_id))

    activity_service.log_activity(
        engagement_id, "engagement", "deletion_cancelled", "Cancelled the pending engagement deletion request"
    )
    db.session.delete(engagement.deletion_request)
    db.session.commit()
    flash("Deletion request cancelled.", "success")
    return redirect(url_for("engagements.engagement_detail", engagement_id=engagement_id))


@bp.route("/<int:engagement_id>/delete/approve", methods=["POST"])
@csrf_protect
def approve_engagement_deletion(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    deletion_request = engagement.deletion_request
    if deletion_request is None:
        flash("There is no pending deletion request for this engagement.", "warning")
        return redirect(url_for("engagements.engagement_detail", engagement_id=engagement_id))

    approver = current_user()
    if approver.role not in (ROLE_ADMIN, ROLE_OPERATOR):
        abort(403)
    if approver.id == deletion_request.requested_by_id:
        flash(
            "The deletion must be approved by a different admin or operator than the one who requested it.",
            "danger",
        )
        return redirect(url_for("engagements.engagement_detail", engagement_id=engagement_id))

    name = engagement.name
    db.session.delete(engagement)
    db.session.commit()
    flash(f"Engagement '{name}' deleted.", "success")
    return redirect(url_for("engagements.list_engagements"))
