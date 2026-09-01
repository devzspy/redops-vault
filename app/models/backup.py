from datetime import datetime, timezone

from app.extensions import db

PROVIDER_AWS = "aws"
PROVIDER_AZURE = "azure"
PROVIDER_GCP = "gcp"
PROVIDER_OCI = "oci"
PROVIDER_SELF_HOSTED = "self_hosted"
PROVIDER_OTHER = "other"
PROVIDERS = (
    PROVIDER_AWS,
    PROVIDER_AZURE,
    PROVIDER_GCP,
    PROVIDER_OCI,
    PROVIDER_SELF_HOSTED,
    PROVIDER_OTHER,
)
PROVIDER_LABELS = {
    PROVIDER_AWS: "Amazon Web Services",
    PROVIDER_AZURE: "Microsoft Azure",
    PROVIDER_GCP: "Google Cloud Platform",
    PROVIDER_OCI: "Oracle Cloud Infrastructure",
    PROVIDER_SELF_HOSTED: "Self-Hosted",
    PROVIDER_OTHER: "Other",
}

STORAGE_TYPE_OBJECT_STORAGE = "object_storage"
STORAGE_TYPE_MANAGED_DATABASE = "managed_database"
STORAGE_TYPE_FILESYSTEM = "filesystem"
STORAGE_TYPES = (
    STORAGE_TYPE_OBJECT_STORAGE,
    STORAGE_TYPE_MANAGED_DATABASE,
    STORAGE_TYPE_FILESYSTEM,
)
STORAGE_TYPE_LABELS = {
    STORAGE_TYPE_OBJECT_STORAGE: "Object / Blob Storage",
    STORAGE_TYPE_MANAGED_DATABASE: "Cloud-Native Database",
    STORAGE_TYPE_FILESYSTEM: "Filesystem / SFTP",
}

SCOPE_FULL_VAULT = "full_vault"
SCOPE_DATABASE_ONLY = "database_only"
SCOPE_LOOT_FILES = "loot_files"
SCOPE_ENGAGEMENT = "engagement"
SCOPES = (SCOPE_FULL_VAULT, SCOPE_DATABASE_ONLY, SCOPE_LOOT_FILES, SCOPE_ENGAGEMENT)
SCOPE_LABELS = {
    SCOPE_FULL_VAULT: "Full Vault (Database + Loot)",
    SCOPE_DATABASE_ONLY: "Database Only",
    SCOPE_LOOT_FILES: "Loot Files Only",
    SCOPE_ENGAGEMENT: "Specific Engagement",
}

FREQUENCY_MANUAL = "manual"
FREQUENCY_HOURLY = "hourly"
FREQUENCY_DAILY = "daily"
FREQUENCY_WEEKLY = "weekly"
FREQUENCY_MONTHLY = "monthly"
FREQUENCIES = (
    FREQUENCY_MANUAL,
    FREQUENCY_HOURLY,
    FREQUENCY_DAILY,
    FREQUENCY_WEEKLY,
    FREQUENCY_MONTHLY,
)
FREQUENCY_LABELS = {
    FREQUENCY_MANUAL: "Manual",
    FREQUENCY_HOURLY: "Hourly",
    FREQUENCY_DAILY: "Daily",
    FREQUENCY_WEEKLY: "Weekly",
    FREQUENCY_MONTHLY: "Monthly",
}

# Seconds between automatic runs for each frequency. FREQUENCY_MANUAL is
# intentionally absent: those destinations are never scheduled, only run
# on demand via "Run Now".
FREQUENCY_INTERVAL_SECONDS = {
    FREQUENCY_HOURLY: 60 * 60,
    FREQUENCY_DAILY: 60 * 60 * 24,
    FREQUENCY_WEEKLY: 60 * 60 * 24 * 7,
    FREQUENCY_MONTHLY: 60 * 60 * 24 * 30,
}

RUN_STATUS_SUCCESS = "success"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_UNKNOWN = "unknown"
RUN_STATUSES = (RUN_STATUS_SUCCESS, RUN_STATUS_FAILED, RUN_STATUS_UNKNOWN)
RUN_STATUS_LABELS = {
    RUN_STATUS_SUCCESS: "Success",
    RUN_STATUS_FAILED: "Failed",
    RUN_STATUS_UNKNOWN: "Unknown",
}

TRIGGER_SCHEDULED = "scheduled"
TRIGGER_MANUAL_RUN = "manual_run"
TRIGGER_MANUAL_LOG = "manual_log"
TRIGGERS = (TRIGGER_SCHEDULED, TRIGGER_MANUAL_RUN, TRIGGER_MANUAL_LOG)
TRIGGER_LABELS = {
    TRIGGER_SCHEDULED: "Scheduled run",
    TRIGGER_MANUAL_RUN: "Manual — Run Now",
    TRIGGER_MANUAL_LOG: "Manually recorded",
}


class BackupDestination(db.Model):
    __tablename__ = "backup_destinations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    provider = db.Column(db.String(20), nullable=False, default=PROVIDER_OTHER)
    storage_type = db.Column(db.String(20), nullable=False, default=STORAGE_TYPE_OBJECT_STORAGE)
    scope = db.Column(db.String(20), nullable=False, default=SCOPE_FULL_VAULT)
    engagement_id = db.Column(db.Integer, db.ForeignKey("engagements.id"), nullable=True, index=True)

    region = db.Column(db.String(80), nullable=True)
    endpoint_url = db.Column(db.String(255), nullable=True)
    bucket_or_resource = db.Column(db.String(255), nullable=True)
    account_identifier = db.Column(db.String(255), nullable=True)
    access_key_id = db.Column(db.String(255), nullable=True)
    secret_encrypted = db.Column(db.LargeBinary, nullable=True)

    frequency = db.Column(db.String(20), nullable=False, default=FREQUENCY_MANUAL)
    retention_days = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    last_backup_at = db.Column(db.DateTime, nullable=True)
    last_backup_status = db.Column(db.String(20), nullable=True)
    last_backup_message = db.Column(db.Text, nullable=True)

    notes = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    engagement = db.relationship("Engagement")
    created_by = db.relationship("User")
    logs = db.relationship(
        "BackupRunLog",
        back_populates="destination",
        cascade="all, delete-orphan",
        order_by="BackupRunLog.ran_at.desc()",
    )

    def provider_label(self):
        return PROVIDER_LABELS.get(self.provider, self.provider)

    def storage_type_label(self):
        return STORAGE_TYPE_LABELS.get(self.storage_type, self.storage_type)

    def scope_label(self):
        return SCOPE_LABELS.get(self.scope, self.scope)

    def frequency_label(self):
        return FREQUENCY_LABELS.get(self.frequency, self.frequency)

    def last_backup_status_label(self):
        return RUN_STATUS_LABELS.get(self.last_backup_status, self.last_backup_status)

    def destination_summary(self):
        parts = [p for p in (self.bucket_or_resource, self.region) if p]
        return " / ".join(parts) if parts else "-"


class BackupRunLog(db.Model):
    """One row per backup run attempt, whether from the APScheduler
    interval trigger, a "Run Now" click, or a manually recorded outcome --
    the history that a single BackupDestination.last_backup_* snapshot
    can't show.
    """

    __tablename__ = "backup_run_logs"

    id = db.Column(db.Integer, primary_key=True)
    destination_id = db.Column(
        db.Integer, db.ForeignKey("backup_destinations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ran_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=True)
    triggered_by = db.Column(db.String(20), nullable=False, default=TRIGGER_SCHEDULED)
    triggered_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    destination = db.relationship("BackupDestination", back_populates="logs")
    triggered_by_user = db.relationship("User")

    def status_label(self):
        return RUN_STATUS_LABELS.get(self.status, self.status)

    def triggered_by_label(self):
        return TRIGGER_LABELS.get(self.triggered_by, self.triggered_by)
