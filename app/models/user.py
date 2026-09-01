from datetime import datetime, timezone

from app.extensions import db

ROLE_OPERATOR = "operator"
ROLE_ADMIN = "admin"
ROLE_AGENT = "agent"
ROLE_BLUETEAM = "blueteam"
ROLES = (ROLE_OPERATOR, ROLE_ADMIN, ROLE_AGENT, ROLE_BLUETEAM)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_OPERATOR)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login_at = db.Column(db.DateTime, nullable=True)

    engagement_assignments = db.relationship(
        "EngagementAssignment",
        foreign_keys="EngagementAssignment.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def is_admin(self):
        return self.role == ROLE_ADMIN

    def is_blueteam(self):
        return self.role == ROLE_BLUETEAM

    def needs_password_change(self):
        return self.must_change_password
