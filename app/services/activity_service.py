from app.auth_utils import current_user
from app.extensions import db
from app.models.activity import ActivityLogEntry

PER_PAGE = 50


def log_activity(
    engagement_id, entity_type, action, summary, occurred_started_at=None, occurred_ended_at=None
):
    """Records one audit-trail entry for an engagement. Called from every
    mutating route right before the enclosing db.session.commit(), so the
    log entry lands in the same transaction as the change it describes.

    created_at (set automatically) is when the entry was recorded in the
    system. occurred_started_at/occurred_ended_at are optional and describe
    when the underlying activity actually took place — useful for
    operator/agent-submitted actions with a real duration (e.g. an nmap
    scan), which can differ from when it was logged.
    """
    actor = current_user()
    entry = ActivityLogEntry(
        engagement_id=engagement_id,
        actor_id=actor.id if actor else None,
        actor_label=actor.username if actor else "system",
        entity_type=entity_type,
        action=action,
        summary=summary,
        occurred_started_at=occurred_started_at,
        occurred_ended_at=occurred_ended_at,
    )
    db.session.add(entry)
    return entry


def recent_activity(engagement_id, limit=PER_PAGE):
    return (
        ActivityLogEntry.query.filter_by(engagement_id=engagement_id)
        .order_by(ActivityLogEntry.created_at.desc(), ActivityLogEntry.id.desc())
        .limit(limit)
        .all()
    )
