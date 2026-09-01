from datetime import datetime, timezone

from app.extensions import db
from app.models.killchain import KILL_CHAIN_MODEL_LMCKC

STATUS_BACKLOG = "backlog"
STATUS_PLANNING = "planning"
STATUS_ACTIVE = "active"
STATUS_COMPLETED = "completed"
STATUSES = (STATUS_BACKLOG, STATUS_PLANNING, STATUS_ACTIVE, STATUS_COMPLETED)

STATUS_LABELS = {
    STATUS_BACKLOG: "Backlog",
    STATUS_PLANNING: "Planning",
    STATUS_ACTIVE: "Active",
    STATUS_COMPLETED: "Completed",
}


class Engagement(db.Model):
    __tablename__ = "engagements"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    client_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_BACKLOG)
    kill_chain_model = db.Column(db.String(20), nullable=False, default=KILL_CHAIN_MODEL_LMCKC)
    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    created_by = db.relationship("User")
    loot_files = db.relationship("LootFile", back_populates="engagement", cascade="all, delete-orphan")
    credentials = db.relationship("Credential", back_populates="engagement", cascade="all, delete-orphan")
    killchain_entries = db.relationship(
        "KillChainEntry", back_populates="engagement", cascade="all, delete-orphan"
    )
    infrastructure_nodes = db.relationship(
        "InfrastructureNode", back_populates="engagement", cascade="all, delete-orphan"
    )
    infrastructure_edges = db.relationship(
        "InfrastructureEdge", back_populates="engagement", cascade="all, delete-orphan"
    )
    findings = db.relationship("Finding", back_populates="engagement", cascade="all, delete-orphan")
    iocs = db.relationship("IOC", back_populates="engagement", cascade="all, delete-orphan")
    activity_log_entries = db.relationship(
        "ActivityLogEntry", back_populates="engagement", cascade="all, delete-orphan"
    )
    todos = db.relationship("Todo", back_populates="engagement", cascade="all, delete-orphan")
    links = db.relationship(
        "EngagementLink",
        back_populates="engagement",
        cascade="all, delete-orphan",
        order_by="EngagementLink.added_at.desc()",
    )
    threat_model = db.relationship(
        "ThreatModel", back_populates="engagement", uselist=False, cascade="all, delete-orphan"
    )
    assignments = db.relationship(
        "EngagementAssignment", back_populates="engagement", cascade="all, delete-orphan"
    )
    deletion_request = db.relationship(
        "EngagementDeletionRequest", back_populates="engagement", uselist=False, cascade="all, delete-orphan"
    )
