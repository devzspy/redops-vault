from datetime import datetime, timezone

from app.extensions import db

HASH_TYPE_MD5 = "md5"
HASH_TYPE_SHA256 = "sha256"
HASH_TYPES = (HASH_TYPE_MD5, HASH_TYPE_SHA256)

HASH_TYPE_LABELS = {
    HASH_TYPE_MD5: "MD5",
    HASH_TYPE_SHA256: "SHA256",
}


class IOC(db.Model):
    __tablename__ = "iocs"

    id = db.Column(db.Integer, primary_key=True)
    engagement_id = db.Column(db.Integer, db.ForeignKey("engagements.id"), nullable=False, index=True)
    host = db.Column(db.String(255), nullable=True)
    location = db.Column(db.String(1000), nullable=True)
    hash_type = db.Column(db.String(20), nullable=True)
    hash_value = db.Column(db.String(128), nullable=True)
    dropped_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    added_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    added_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    engagement = db.relationship("Engagement", back_populates="iocs")
    added_by = db.relationship("User")

    def hash_type_label(self):
        return HASH_TYPE_LABELS.get(self.hash_type, self.hash_type)

    def display_label(self):
        return self.location or self.host or "(unnamed IOC)"
