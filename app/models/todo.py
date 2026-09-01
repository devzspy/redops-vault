from datetime import datetime, timezone

from app.extensions import db

STATUS_OPEN = "open"
STATUS_DONE = "done"
STATUSES = (STATUS_OPEN, STATUS_DONE)

STATUS_LABELS = {
    STATUS_OPEN: "Open",
    STATUS_DONE: "Done",
}


class Todo(db.Model):
    """A checklist item for an engagement. status tracks open/done; whether
    it's "in progress" vs. just "open" is derived from whether assignee_id
    is set, rather than being its own status — an open task with an
    assignee is being worked, an open task without one is up for grabs
    (including tasks that were explicitly handed off).
    """

    __tablename__ = "todos"

    id = db.Column(db.Integer, primary_key=True)
    engagement_id = db.Column(db.Integer, db.ForeignKey("engagements.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_OPEN)
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    handoff_notes = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    completed_at = db.Column(db.DateTime, nullable=True)
    completed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    engagement = db.relationship("Engagement", back_populates="todos")
    assignee = db.relationship("User", foreign_keys=[assignee_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    completed_by = db.relationship("User", foreign_keys=[completed_by_id])

    def status_label(self):
        return STATUS_LABELS.get(self.status, self.status)

    def is_in_progress(self):
        return self.status == STATUS_OPEN and self.assignee_id is not None

    def is_available(self):
        return self.status == STATUS_OPEN and self.assignee_id is None
