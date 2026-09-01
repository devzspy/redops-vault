from datetime import datetime, timezone

from app.extensions import db

NODE_TYPE_HOSTNAME = "hostname"
NODE_TYPE_IP_ADDRESS = "ip_address"
NODE_TYPE_DOMAIN = "domain"
NODE_TYPE_REGION = "region"
NODE_TYPE_CLOUD_PROVIDER = "cloud_provider"
NODE_TYPES = (
    NODE_TYPE_HOSTNAME,
    NODE_TYPE_IP_ADDRESS,
    NODE_TYPE_DOMAIN,
    NODE_TYPE_REGION,
    NODE_TYPE_CLOUD_PROVIDER,
)

# Additional node types for the Targets & Victims pane: the data-storage,
# collaboration, and knowledge-management platforms a target organization
# runs internally, which attackers pivot to once inside (file shares, wikis,
# runbooks, ticketing, etc.), distinct from plain hosts/IPs/domains.
NODE_TYPE_FILE_SHARE = "file_share"
NODE_TYPE_CLOUD_STORAGE = "cloud_storage"
NODE_TYPE_DATABASE = "database"
NODE_TYPE_WIKI = "wiki"
NODE_TYPE_SOURCE_CONTROL = "source_control"
NODE_TYPE_TICKETING = "ticketing"
NODE_TYPE_COLLABORATION = "collaboration"
NODE_TYPE_BACKUP_SYSTEM = "backup_system"

TARGET_NODE_TYPES = NODE_TYPES + (
    NODE_TYPE_FILE_SHARE,
    NODE_TYPE_CLOUD_STORAGE,
    NODE_TYPE_DATABASE,
    NODE_TYPE_WIKI,
    NODE_TYPE_SOURCE_CONTROL,
    NODE_TYPE_TICKETING,
    NODE_TYPE_COLLABORATION,
    NODE_TYPE_BACKUP_SYSTEM,
)

NODE_TYPE_LABELS = {
    NODE_TYPE_HOSTNAME: "Hostname",
    NODE_TYPE_IP_ADDRESS: "IP Address",
    NODE_TYPE_DOMAIN: "Domain",
    NODE_TYPE_REGION: "Region / Realm",
    NODE_TYPE_CLOUD_PROVIDER: "Cloud Provider",
    NODE_TYPE_FILE_SHARE: "File Share (SMB/NFS)",
    NODE_TYPE_CLOUD_STORAGE: "Cloud Storage (S3/Blob/GCS)",
    NODE_TYPE_DATABASE: "Database",
    NODE_TYPE_WIKI: "Wiki / Documentation",
    NODE_TYPE_SOURCE_CONTROL: "Source Control (Git)",
    NODE_TYPE_TICKETING: "Ticketing / ITSM",
    NODE_TYPE_COLLABORATION: "Collaboration (Email/Chat)",
    NODE_TYPE_BACKUP_SYSTEM: "Backup System",
}

ROLE_REDIRECTOR = "redirector"
ROLE_TEAM_SERVER = "team_server"
ROLE_TARGET = "target"
ROLE_VICTIM = "victim"
ROLE_PIVOT = "pivot"
ROLE_PROXY = "proxy"
ROLE_C2 = "C2"
ROLE_OSINT = "OSINT"
ROLE_OTHER = "other"
ROLES = (
    ROLE_REDIRECTOR,
    ROLE_TEAM_SERVER,
    ROLE_TARGET,
    ROLE_VICTIM,
    ROLE_PIVOT,
    ROLE_PROXY,
    ROLE_C2,
    ROLE_OSINT,
    ROLE_OTHER,
)

# Nodes with these roles live on the Targets & Victims pane, separate from
# attacker-owned/operated infrastructure.
TARGET_ROLES = (ROLE_TARGET, ROLE_VICTIM)

# Roles selectable on the Infrastructure pane (everything except targets/victims,
# which are managed exclusively from the Targets & Victims pane).
ATTACKER_ROLES = tuple(r for r in ROLES if r not in TARGET_ROLES)

STATUS_HEALTHY = "healthy"
STATUS_ISOLATED = "isolated"
STATUS_DEAD = "dead"
STATUS_BURNED = "burned"

# Targets/victims track access state; attacker infrastructure tracks
# whether it's still safe to use.
TARGET_STATUSES = (STATUS_HEALTHY, STATUS_ISOLATED, STATUS_DEAD)
INFRA_STATUSES = (STATUS_HEALTHY, STATUS_BURNED)


class InfrastructureNode(db.Model):
    __tablename__ = "infrastructure_nodes"

    id = db.Column(db.Integer, primary_key=True)
    engagement_id = db.Column(db.Integer, db.ForeignKey("engagements.id"), nullable=False, index=True)
    node_type = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(20), nullable=True, default=STATUS_HEALTHY)
    provider = db.Column(db.String(120), nullable=True)
    region = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    added_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    added_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    engagement = db.relationship("Engagement", back_populates="infrastructure_nodes")
    added_by = db.relationship("User")
    services = db.relationship(
        "InfrastructureService",
        back_populates="node",
        cascade="all, delete-orphan",
        order_by="InfrastructureService.name",
    )


class InfrastructureService(db.Model):
    __tablename__ = "infrastructure_services"

    id = db.Column(db.Integer, primary_key=True)
    node_id = db.Column(db.Integer, db.ForeignKey("infrastructure_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    port = db.Column(db.Integer, nullable=True)
    added_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    node = db.relationship("InfrastructureNode", back_populates="services")

    def display(self):
        return f"{self.name}:{self.port}" if self.port is not None else self.name


class InfrastructureEdge(db.Model):
    __tablename__ = "infrastructure_edges"

    id = db.Column(db.Integer, primary_key=True)
    engagement_id = db.Column(db.Integer, db.ForeignKey("engagements.id"), nullable=False, index=True)
    source_node_id = db.Column(
        db.Integer, db.ForeignKey("infrastructure_nodes.id", ondelete="CASCADE"), nullable=False
    )
    target_node_id = db.Column(
        db.Integer, db.ForeignKey("infrastructure_nodes.id", ondelete="CASCADE"), nullable=False
    )
    label = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    added_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    added_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    engagement = db.relationship("Engagement", back_populates="infrastructure_edges")
    source_node = db.relationship("InfrastructureNode", foreign_keys=[source_node_id])
    target_node = db.relationship("InfrastructureNode", foreign_keys=[target_node_id])
    added_by = db.relationship("User")
