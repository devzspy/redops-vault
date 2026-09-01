from datetime import datetime, timezone

from app.extensions import db


class ActivityLogEntry(db.Model):
    __tablename__ = "activity_log_entries"

    id = db.Column(db.Integer, primary_key=True)
    engagement_id = db.Column(db.Integer, db.ForeignKey("engagements.id"), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    actor_label = db.Column(db.String(80), nullable=False)
    entity_type = db.Column(db.String(30), nullable=False)
    action = db.Column(db.String(20), nullable=False)
    summary = db.Column(db.String(500), nullable=False)
    occurred_started_at = db.Column(db.DateTime, nullable=True)
    occurred_ended_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    engagement = db.relationship("Engagement", back_populates="activity_log_entries")
    actor = db.relationship("User")

    def occurred_range_label(self):
        if not self.occurred_started_at:
            return None
        if not self.occurred_ended_at:
            return self.occurred_started_at.strftime("%Y-%m-%d %H:%M")
        if self.occurred_started_at.date() == self.occurred_ended_at.date():
            return (
                f"{self.occurred_started_at.strftime('%Y-%m-%d %H:%M')}"
                f" – {self.occurred_ended_at.strftime('%H:%M')}"
            )
        return (
            f"{self.occurred_started_at.strftime('%Y-%m-%d %H:%M')}"
            f" – {self.occurred_ended_at.strftime('%Y-%m-%d %H:%M')}"
        )
