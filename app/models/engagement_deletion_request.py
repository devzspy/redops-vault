from datetime import datetime, timezone

from app.extensions import db


class EngagementDeletionRequest(db.Model):
    __tablename__ = "engagement_deletion_requests"

    id = db.Column(db.Integer, primary_key=True)
    engagement_id = db.Column(
        db.Integer, db.ForeignKey("engagements.id"), nullable=False, unique=True, index=True
    )
    requested_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    requested_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    engagement = db.relationship("Engagement", back_populates="deletion_request")
    requested_by = db.relationship("User", foreign_keys=[requested_by_id])
