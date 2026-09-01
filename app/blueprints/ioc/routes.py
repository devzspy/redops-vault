from datetime import datetime

from flask import abort, flash, redirect, render_template, request, url_for
from flask_jwt_extended import jwt_required

from app.auth_utils import csrf_protect, current_user
from app.blueprints.ioc import bp
from app.extensions import db
from app.models.engagement import Engagement
from app.models.infrastructure import ROLE_TARGET, InfrastructureNode
from app.models.ioc import HASH_TYPES, IOC
from app.services import activity_service


def _parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


def _target_nodes(engagement_id):
    return (
        InfrastructureNode.query.filter_by(engagement_id=engagement_id, role=ROLE_TARGET)
        .order_by(InfrastructureNode.name.asc())
        .all()
    )


@bp.route("/engagements/<int:engagement_id>/iocs")
@jwt_required()
def list_iocs(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    iocs = (
        IOC.query.filter_by(engagement_id=engagement_id)
        .order_by(IOC.dropped_at.desc().nullslast(), IOC.added_at.desc())
        .all()
    )
    return render_template("iocs/list.html", engagement=engagement, iocs=iocs)


@bp.route("/engagements/<int:engagement_id>/iocs/new")
@jwt_required()
def new_ioc_form(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return render_template(
        "iocs/form.html",
        engagement=engagement,
        ioc=None,
        hash_types=HASH_TYPES,
        nodes=_target_nodes(engagement_id),
    )


@bp.route("/engagements/<int:engagement_id>/iocs", methods=["POST"])
@csrf_protect
def create_ioc(engagement_id):
    Engagement.query.get_or_404(engagement_id)

    hash_type = request.form.get("hash_type") or None
    if hash_type and hash_type not in HASH_TYPES:
        abort(400, description="Invalid hash type")

    ioc = IOC(
        engagement_id=engagement_id,
        host=request.form.get("host", "").strip() or None,
        location=request.form.get("location", "").strip() or None,
        hash_type=hash_type,
        hash_value=request.form.get("hash_value", "").strip() or None,
        dropped_at=_parse_datetime(request.form.get("dropped_at")),
        notes=request.form.get("notes", "").strip() or None,
        added_by_id=int(current_user().id),
    )
    db.session.add(ioc)
    db.session.flush()
    activity_service.log_activity(engagement_id, "ioc", "created", f"Added IOC '{ioc.display_label()}'")
    db.session.commit()
    flash("IOC added.", "success")
    return redirect(url_for("ioc.list_iocs", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/iocs/<int:ioc_id>/edit")
@jwt_required()
def edit_ioc_form(engagement_id, ioc_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    ioc = IOC.query.filter_by(id=ioc_id, engagement_id=engagement_id).first_or_404()
    return render_template(
        "iocs/form.html",
        engagement=engagement,
        ioc=ioc,
        hash_types=HASH_TYPES,
        nodes=_target_nodes(engagement_id),
    )


@bp.route("/engagements/<int:engagement_id>/iocs/<int:ioc_id>/edit", methods=["POST"])
@csrf_protect
def edit_ioc(engagement_id, ioc_id):
    ioc = IOC.query.filter_by(id=ioc_id, engagement_id=engagement_id).first_or_404()

    hash_type = request.form.get("hash_type") or None
    if hash_type and hash_type not in HASH_TYPES:
        abort(400, description="Invalid hash type")

    ioc.host = request.form.get("host", "").strip() or None
    ioc.location = request.form.get("location", "").strip() or None
    ioc.hash_type = hash_type
    ioc.hash_value = request.form.get("hash_value", "").strip() or None
    ioc.dropped_at = _parse_datetime(request.form.get("dropped_at"))
    ioc.notes = request.form.get("notes", "").strip() or None
    activity_service.log_activity(engagement_id, "ioc", "updated", f"Updated IOC '{ioc.display_label()}'")
    db.session.commit()
    flash("IOC updated.", "success")
    return redirect(url_for("ioc.list_iocs", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/iocs/<int:ioc_id>/delete", methods=["POST"])
@csrf_protect
def delete_ioc(engagement_id, ioc_id):
    ioc = IOC.query.filter_by(id=ioc_id, engagement_id=engagement_id).first_or_404()
    activity_service.log_activity(engagement_id, "ioc", "deleted", f"Deleted IOC '{ioc.display_label()}'")
    db.session.delete(ioc)
    db.session.commit()
    flash("IOC deleted.", "success")
    return redirect(url_for("ioc.list_iocs", engagement_id=engagement_id))
