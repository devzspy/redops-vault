from datetime import datetime, timezone

from app.extensions import db

LINK_TYPE_EXTERNAL = "external"
LINK_TYPE_INTERNAL = "internal"
LINK_TYPES = (LINK_TYPE_EXTERNAL, LINK_TYPE_INTERNAL)

LINK_TYPE_LABELS = {
    LINK_TYPE_EXTERNAL: "External",
    LINK_TYPE_INTERNAL: "Internal",
}


class EngagementLink(db.Model):
    __tablename__ = "engagement_links"

    id = db.Column(db.Integer, primary_key=True)
    engagement_id = db.Column(db.Integer, db.ForeignKey("engagements.id"), nullable=False, index=True)
    link_type = db.Column(db.String(20), nullable=False, default=LINK_TYPE_EXTERNAL)
    url = db.Column(db.String(2048), nullable=False)
    label = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    added_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    added_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    engagement = db.relationship("Engagement", back_populates="links")
    added_by = db.relationship("User")

    def link_type_label(self):
        return LINK_TYPE_LABELS.get(self.link_type, self.link_type)

    def display_label(self):
        return self.label or self.url
