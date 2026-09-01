"""In-process job scheduler for automatic backup runs. Uses APScheduler's
BackgroundScheduler, which is enough for this single-process, self-hosted
Flask app (see init_scheduler for the reloader guard). If this app is ever
run under a multi-process WSGI server (gunicorn -w N), each worker would
start its own scheduler and duplicate runs; that would need an external
job store / leader election, out of scope here.
"""

import atexit
import logging
import os
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.extensions import db
from app.models.backup import (
    FREQUENCY_INTERVAL_SECONDS,
    RUN_STATUS_FAILED,
    RUN_STATUS_SUCCESS,
    TRIGGER_SCHEDULED,
    BackupDestination,
    BackupRunLog,
)
from app.services import backup_service, backup_transport

logger = logging.getLogger(__name__)

_scheduler = None
_app = None


def init_scheduler(app):
    global _scheduler, _app

    if app.config.get("TESTING"):
        return
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        # Under the Werkzeug debug reloader, create_app() runs once in the
        # watcher process and once in the worker process; only the worker
        # actually serves requests, so only it should run the scheduler.
        return

    _app = app
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.start()
    atexit.register(lambda: _scheduler.shutdown(wait=False))

    with app.app_context():
        for destination in BackupDestination.query.filter_by(is_active=True).all():
            _schedule_job(destination)


def sync_job(destination):
    """Add, replace, or remove the scheduled job for one destination based
    on its current is_active flag and frequency. Call this right after any
    create/edit so the running schedule matches the database.
    """
    if _scheduler is None:
        return
    remove_job(destination.id)
    if destination.is_active:
        _schedule_job(destination)


def remove_job(destination_id):
    if _scheduler is None:
        return
    job_id = _job_id(destination_id)
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)


def _job_id(destination_id):
    return f"backup-{destination_id}"


def _schedule_job(destination):
    seconds = FREQUENCY_INTERVAL_SECONDS.get(destination.frequency)
    if not seconds:
        return
    _scheduler.add_job(
        run_backup,
        trigger=IntervalTrigger(seconds=seconds),
        id=_job_id(destination.id),
        args=[destination.id],
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )


def run_backup(destination_id, triggered_by=TRIGGER_SCHEDULED, triggered_by_user_id=None):
    """Builds the archive, uploads it, and records the outcome (both on the
    destination's last-run snapshot and as a BackupRunLog row). Safe to
    call directly for a manual "Run Now" (inside a request's app context)
    or from an APScheduler job (which has none of its own).
    """
    app = _app
    if app is None:
        from flask import current_app

        app = current_app._get_current_object()

    with app.app_context():
        destination = BackupDestination.query.get(destination_id)
        if destination is None:
            return

        local_path = None
        try:
            local_path = backup_service.build_archive(destination)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            remote_filename = f"{_safe_name(destination.name)}-{timestamp}.zip"
            backup_transport.upload(destination, local_path, remote_filename)

            ran_at = datetime.now(timezone.utc)
            message = f"Uploaded {remote_filename}"
            destination.last_backup_at = ran_at
            destination.last_backup_status = RUN_STATUS_SUCCESS
            destination.last_backup_message = message
            db.session.add(
                BackupRunLog(
                    destination_id=destination_id, ran_at=ran_at, status=RUN_STATUS_SUCCESS,
                    message=message, triggered_by=triggered_by, triggered_by_user_id=triggered_by_user_id,
                )
            )
            db.session.commit()
        except Exception as exc:
            logger.exception("Backup run failed for destination %s", destination_id)
            db.session.rollback()
            destination = BackupDestination.query.get(destination_id)
            if destination is not None:
                ran_at = datetime.now(timezone.utc)
                message = str(exc)
                destination.last_backup_at = ran_at
                destination.last_backup_status = RUN_STATUS_FAILED
                destination.last_backup_message = message
                db.session.add(
                    BackupRunLog(
                        destination_id=destination_id, ran_at=ran_at, status=RUN_STATUS_FAILED,
                        message=message, triggered_by=triggered_by, triggered_by_user_id=triggered_by_user_id,
                    )
                )
                db.session.commit()
        finally:
            if local_path and os.path.exists(local_path):
                os.remove(local_path)


def _safe_name(name):
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in name).strip("-") or "backup"
