from datetime import datetime, timezone

from app.extensions import db


class EngagementAssignment(db.Model):
    __tablename__ = "engagement_assignments"
    __table_args__ = (db.UniqueConstraint("engagement_id", "user_id", name="uq_engagement_assignment"),)

    id = db.Column(db.Integer, primary_key=True)
    engagement_id = db.Column(db.Integer, db.ForeignKey("engagements.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    assigned_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    engagement = db.relationship("Engagement", back_populates="assignments")
    user = db.relationship("User", foreign_keys=[user_id], back_populates="engagement_assignments")
    assigned_by = db.relationship("User", foreign_keys=[assigned_by_id])
