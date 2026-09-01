from datetime import datetime, timezone

from app.extensions import db


class ThreatModel(db.Model):
    """The operator-authored planning document for an engagement: the
    adversary being emulated, the planned attack path, and the objectives
    that define success. One per engagement, created lazily on first save.
    """

    __tablename__ = "threat_models"

    id = db.Column(db.Integer, primary_key=True)
    engagement_id = db.Column(
        db.Integer, db.ForeignKey("engagements.id"), nullable=False, unique=True, index=True
    )
    threat_model = db.Column(db.Text, nullable=True)
    attack_plan = db.Column(db.Text, nullable=True)
    objectives = db.Column(db.Text, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    engagement = db.relationship("Engagement", back_populates="threat_model")
    updated_by = db.relationship("User")

    def is_empty(self):
        return not (self.threat_model or self.attack_plan or self.objectives)
