from datetime import datetime, timezone

from flask import abort, flash, redirect, render_template, request, url_for
from flask_jwt_extended import jwt_required

from app.auth_utils import csrf_protect, current_user
from app.blueprints.backups import bp
from app.extensions import db
from app.models.backup import (
    FREQUENCIES,
    FREQUENCY_MANUAL,
    PROVIDERS,
    PROVIDER_OTHER,
    RUN_STATUS_FAILED,
    RUN_STATUS_SUCCESS,
    SCOPES,
    SCOPE_ENGAGEMENT,
    SCOPE_FULL_VAULT,
    STORAGE_TYPES,
    STORAGE_TYPE_OBJECT_STORAGE,
    TRIGGER_MANUAL_LOG,
    TRIGGER_MANUAL_RUN,
    BackupDestination,
    BackupRunLog,
)
from app.models.engagement import Engagement
from app.services import crypto_service, scheduler_service


def _engagements():
    return Engagement.query.order_by(Engagement.name.asc()).all()


@bp.route("")
@jwt_required()
def list_backups():
    destinations = BackupDestination.query.order_by(BackupDestination.name.asc()).all()
    return render_template("backups/list.html", destinations=destinations)


@bp.route("/new")
@jwt_required()
def new_backup_form():
    return render_template(
        "backups/form.html",
        destination=None,
        providers=PROVIDERS,
        storage_types=STORAGE_TYPES,
        scopes=SCOPES,
        frequencies=FREQUENCIES,
        engagements=_engagements(),
    )


@bp.route("", methods=["POST"])
@csrf_protect
def create_backup():
    name = request.form.get("name", "").strip()
    provider = request.form.get("provider", PROVIDER_OTHER)
    storage_type = request.form.get("storage_type", STORAGE_TYPE_OBJECT_STORAGE)
    scope = request.form.get("scope", SCOPE_FULL_VAULT)
    frequency = request.form.get("frequency", FREQUENCY_MANUAL)

    if not name:
        flash("Name is required.", "danger")
        return redirect(url_for("backups.new_backup_form"))
    if provider not in PROVIDERS:
        abort(400, description="Invalid provider")
    if storage_type not in STORAGE_TYPES:
        abort(400, description="Invalid storage type")
    if scope not in SCOPES:
        abort(400, description="Invalid scope")
    if frequency not in FREQUENCIES:
        abort(400, description="Invalid frequency")

    engagement_id = request.form.get("engagement_id") or None
    if scope != SCOPE_ENGAGEMENT:
        engagement_id = None
    elif engagement_id:
        Engagement.query.get_or_404(int(engagement_id))

    retention_days = request.form.get("retention_days") or None

    secret = request.form.get("secret", "")

    destination = BackupDestination(
        name=name,
        provider=provider,
        storage_type=storage_type,
        scope=scope,
        engagement_id=int(engagement_id) if engagement_id else None,
        region=request.form.get("region", "").strip() or None,
        endpoint_url=request.form.get("endpoint_url", "").strip() or None,
        bucket_or_resource=request.form.get("bucket_or_resource", "").strip() or None,
        account_identifier=request.form.get("account_identifier", "").strip() or None,
        access_key_id=request.form.get("access_key_id", "").strip() or None,
        secret_encrypted=crypto_service.encrypt_field(secret) if secret else None,
        frequency=frequency,
        retention_days=int(retention_days) if retention_days else None,
        is_active=request.form.get("is_active") == "on",
        notes=request.form.get("notes", "").strip() or None,
        created_by_id=int(current_user().id),
    )
    db.session.add(destination)
    db.session.commit()
    scheduler_service.sync_job(destination)
    flash(f"Backup destination '{name}' added.", "success")
    return redirect(url_for("backups.list_backups"))


@bp.route("/<int:backup_id>/edit")
@jwt_required()
def edit_backup_form(backup_id):
    destination = BackupDestination.query.get_or_404(backup_id)
    return render_template(
        "backups/form.html",
        destination=destination,
        providers=PROVIDERS,
        storage_types=STORAGE_TYPES,
        scopes=SCOPES,
        frequencies=FREQUENCIES,
        engagements=_engagements(),
    )


@bp.route("/<int:backup_id>/edit", methods=["POST"])
@csrf_protect
def edit_backup(backup_id):
    destination = BackupDestination.query.get_or_404(backup_id)

    name = request.form.get("name", "").strip()
    provider = request.form.get("provider", destination.provider)
    storage_type = request.form.get("storage_type", destination.storage_type)
    scope = request.form.get("scope", destination.scope)
    frequency = request.form.get("frequency", destination.frequency)

    if not name:
        flash("Name is required.", "danger")
        return redirect(url_for("backups.edit_backup_form", backup_id=backup_id))
    if provider not in PROVIDERS:
        abort(400, description="Invalid provider")
    if storage_type not in STORAGE_TYPES:
        abort(400, description="Invalid storage type")
    if scope not in SCOPES:
        abort(400, description="Invalid scope")
    if frequency not in FREQUENCIES:
        abort(400, description="Invalid frequency")

    engagement_id = request.form.get("engagement_id") or None
    if scope != SCOPE_ENGAGEMENT:
        engagement_id = None
    elif engagement_id:
        Engagement.query.get_or_404(int(engagement_id))

    retention_days = request.form.get("retention_days") or None
    secret = request.form.get("secret", "")

    destination.name = name
    destination.provider = provider
    destination.storage_type = storage_type
    destination.scope = scope
    destination.engagement_id = int(engagement_id) if engagement_id else None
    destination.region = request.form.get("region", "").strip() or None
    destination.endpoint_url = request.form.get("endpoint_url", "").strip() or None
    destination.bucket_or_resource = request.form.get("bucket_or_resource", "").strip() or None
    destination.account_identifier = request.form.get("account_identifier", "").strip() or None
    destination.access_key_id = request.form.get("access_key_id", "").strip() or None
    if secret:
        destination.secret_encrypted = crypto_service.encrypt_field(secret)
    destination.frequency = frequency
    destination.retention_days = int(retention_days) if retention_days else None
    destination.is_active = request.form.get("is_active") == "on"
    destination.notes = request.form.get("notes", "").strip() or None
    db.session.commit()
    scheduler_service.sync_job(destination)
    flash(f"Backup destination '{destination.name}' updated.", "success")
    return redirect(url_for("backups.list_backups"))


@bp.route("/<int:backup_id>/run-now", methods=["POST"])
@csrf_protect
def run_backup_now(backup_id):
    destination = BackupDestination.query.get_or_404(backup_id)
    scheduler_service.run_backup(
        backup_id, triggered_by=TRIGGER_MANUAL_RUN, triggered_by_user_id=int(current_user().id)
    )
    db.session.refresh(destination)
    if destination.last_backup_status == RUN_STATUS_SUCCESS:
        flash(f"Backup run for '{destination.name}' succeeded.", "success")
    else:
        flash(f"Backup run for '{destination.name}' failed: {destination.last_backup_message}", "danger")
    return redirect(url_for("backups.list_backups"))


@bp.route("/<int:backup_id>/record-run", methods=["POST"])
@csrf_protect
def record_backup_run(backup_id):
    destination = BackupDestination.query.get_or_404(backup_id)
    outcome = request.form.get("outcome")
    if outcome not in (RUN_STATUS_SUCCESS, RUN_STATUS_FAILED):
        abort(400, description="Invalid outcome")

    ran_at = datetime.now(timezone.utc)
    destination.last_backup_at = ran_at
    destination.last_backup_status = outcome
    db.session.add(
        BackupRunLog(
            destination_id=destination.id, ran_at=ran_at, status=outcome,
            triggered_by=TRIGGER_MANUAL_LOG, triggered_by_user_id=int(current_user().id),
        )
    )
    db.session.commit()
    flash(f"Recorded {outcome} backup run for '{destination.name}'.", "success")
    return redirect(url_for("backups.list_backups"))


@bp.route("/<int:backup_id>/delete", methods=["POST"])
@csrf_protect
def delete_backup(backup_id):
    destination = BackupDestination.query.get_or_404(backup_id)
    name = destination.name
    db.session.delete(destination)
    db.session.commit()
    scheduler_service.remove_job(backup_id)
    flash(f"Backup destination '{name}' deleted.", "success")
    return redirect(url_for("backups.list_backups"))
