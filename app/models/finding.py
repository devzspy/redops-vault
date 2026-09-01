from datetime import datetime, timezone

from app.extensions import db

SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"
SEVERITY_INFORMATIONAL = "informational"

SEVERITIES = (
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    SEVERITY_LOW,
    SEVERITY_INFORMATIONAL,
)

SEVERITY_LABELS = {
    SEVERITY_CRITICAL: "Critical",
    SEVERITY_HIGH: "High",
    SEVERITY_MEDIUM: "Medium",
    SEVERITY_LOW: "Low",
    SEVERITY_INFORMATIONAL: "Informational",
}

# Lower rank = more severe; used to sort findings for the report/list.
SEVERITY_RANK = {severity: i for i, severity in enumerate(SEVERITIES)}

finding_loot = db.Table(
    "finding_loot",
    db.Column("finding_id", db.Integer, db.ForeignKey("findings.id"), primary_key=True),
    db.Column("loot_file_id", db.Integer, db.ForeignKey("loot_files.id"), primary_key=True),
)

finding_infra_node = db.Table(
    "finding_infra_node",
    db.Column("finding_id", db.Integer, db.ForeignKey("findings.id"), primary_key=True),
    db.Column("infra_node_id", db.Integer, db.ForeignKey("infrastructure_nodes.id"), primary_key=True),
)

finding_credential = db.Table(
    "finding_credential",
    db.Column("finding_id", db.Integer, db.ForeignKey("findings.id"), primary_key=True),
    db.Column("credential_id", db.Integer, db.ForeignKey("credentials.id"), primary_key=True),
)

finding_ioc = db.Table(
    "finding_ioc",
    db.Column("finding_id", db.Integer, db.ForeignKey("findings.id"), primary_key=True),
    db.Column("ioc_id", db.Integer, db.ForeignKey("iocs.id"), primary_key=True),
)

finding_killchain_entry = db.Table(
    "finding_killchain_entry",
    db.Column("finding_id", db.Integer, db.ForeignKey("findings.id"), primary_key=True),
    db.Column("killchain_entry_id", db.Integer, db.ForeignKey("killchain_entries.id"), primary_key=True),
)


class Finding(db.Model):
    __tablename__ = "findings"

    id = db.Column(db.Integer, primary_key=True)
    engagement_id = db.Column(db.Integer, db.ForeignKey("engagements.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    severity = db.Column(db.String(20), nullable=False, default=SEVERITY_MEDIUM)
    details = db.Column(db.Text, nullable=True)
    remediation = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    engagement = db.relationship("Engagement", back_populates="findings")
    created_by = db.relationship("User")
    loot_files = db.relationship("LootFile", secondary=finding_loot)
    infra_nodes = db.relationship("InfrastructureNode", secondary=finding_infra_node, backref="findings")
    credentials = db.relationship("Credential", secondary=finding_credential, backref="findings")
    iocs = db.relationship("IOC", secondary=finding_ioc, backref="findings")
    killchain_entries = db.relationship("KillChainEntry", secondary=finding_killchain_entry, backref="findings")

    def severity_label(self):
        return SEVERITY_LABELS.get(self.severity, self.severity)

    def severity_rank(self):
        return SEVERITY_RANK.get(self.severity, len(SEVERITIES))
