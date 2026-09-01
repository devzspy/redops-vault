from datetime import datetime, timezone

from sqlalchemy import event

from app.extensions import db

CATEGORY_DOCUMENT = "document"
CATEGORY_SCREENSHOT = "screenshot"
CATEGORY_PCAP = "pcap"
CATEGORY_KEY_CERT = "key_cert"
CATEGORY_NOTE = "note"
CATEGORY_OTHER = "other"
CATEGORIES = (
    CATEGORY_DOCUMENT,
    CATEGORY_SCREENSHOT,
    CATEGORY_PCAP,
    CATEGORY_KEY_CERT,
    CATEGORY_NOTE,
    CATEGORY_OTHER,
)


class LootFile(db.Model):
    __tablename__ = "loot_files"

    id = db.Column(db.Integer, primary_key=True)
    engagement_id = db.Column(db.Integer, db.ForeignKey("engagements.id"), nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    # Exactly one of these is populated per row, depending on dialect: Postgres
    # streams file bytes into a Large Object (content_oid, up to 4 TB, true
    # chunked read/write); SQLite (test-only -- Large Objects are a Postgres
    # feature) falls back to storing bytes directly in encrypted_content.
    content_oid = db.Column(db.BigInteger, nullable=True)
    encrypted_content = db.Column(db.LargeBinary, nullable=True)
    category = db.Column(db.String(20), nullable=False, default=CATEGORY_OTHER)
    description = db.Column(db.Text, nullable=True)
    tags = db.Column(db.String(500), nullable=True)
    associated_host = db.Column(db.String(255), nullable=True)
    file_size_bytes = db.Column(db.BigInteger, nullable=False, default=0)
    content_type = db.Column(db.String(120), nullable=True)
    sha256_plaintext = db.Column(db.String(64), nullable=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    engagement = db.relationship("Engagement", back_populates="loot_files")
    uploaded_by = db.relationship("User")
    technique_mappings = db.relationship(
        "TechniqueMapping", back_populates="loot_file", cascade="all, delete-orphan"
    )

    def tag_list(self):
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]


@event.listens_for(LootFile, "before_delete")
def _unlink_large_object_on_delete(mapper, connection, target):
    """Postgres won't garbage-collect a Large Object when the row pointing
    at it is deleted -- it has to be unlinked explicitly. Doing it here
    (rather than at each delete call site) covers both a direct loot
    delete and an Engagement cascade delete, since cascade="all,
    delete-orphan" makes SQLAlchemy emit one ORM-level DELETE per row.
    """
    if target.content_oid is None:
        return
    raw = connection.connection
    if getattr(raw, "dbapi_connection", None) is None:
        return
    raw.lobject(target.content_oid, mode="n").unlink()


CRED_TYPE_PASSWORD = "password"
CRED_TYPE_API_KEY = "api_key"
CRED_TYPE_SSH_KEY = "ssh_key"
CREDENTIAL_TYPES = (CRED_TYPE_PASSWORD, CRED_TYPE_API_KEY, CRED_TYPE_SSH_KEY)
CREDENTIAL_TYPE_LABELS = {
    CRED_TYPE_PASSWORD: "Username / Password",
    CRED_TYPE_API_KEY: "API Key",
    CRED_TYPE_SSH_KEY: "SSH Key",
}

CRED_STATUS_UNTESTED = "untested"
CRED_STATUS_WORKING = "working"
CRED_STATUS_NOT_WORKING = "not_working"
CREDENTIAL_STATUSES = (CRED_STATUS_UNTESTED, CRED_STATUS_WORKING, CRED_STATUS_NOT_WORKING)
CREDENTIAL_STATUS_LABELS = {
    CRED_STATUS_UNTESTED: "Untested",
    CRED_STATUS_WORKING: "Working",
    CRED_STATUS_NOT_WORKING: "Not Working",
}


class Credential(db.Model):
    __tablename__ = "credentials"

    id = db.Column(db.Integer, primary_key=True)
    engagement_id = db.Column(db.Integer, db.ForeignKey("engagements.id"), nullable=False, index=True)
    credential_type = db.Column(db.String(20), nullable=False, default=CRED_TYPE_PASSWORD)
    username = db.Column(db.String(255), nullable=True)
    password_encrypted = db.Column(db.LargeBinary, nullable=True)
    hash_encrypted = db.Column(db.LargeBinary, nullable=True)
    api_key_encrypted = db.Column(db.LargeBinary, nullable=True)
    ssh_private_key_encrypted = db.Column(db.LargeBinary, nullable=True)
    ssh_passphrase_encrypted = db.Column(db.LargeBinary, nullable=True)
    totp_secret_encrypted = db.Column(db.LargeBinary, nullable=True)
    domain = db.Column(db.String(255), nullable=True)
    source_host = db.Column(db.String(255), nullable=True)
    access_description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=CRED_STATUS_UNTESTED)
    notes = db.Column(db.Text, nullable=True)
    added_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    added_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    engagement = db.relationship("Engagement", back_populates="credentials")
    added_by = db.relationship("User")

    def display_label(self):
        label = self.username or "(no username)"
        if self.domain:
            label = f"{self.domain}\\{label}"
        if self.source_host:
            label = f"{label} @ {self.source_host}"
        return label

    def credential_type_label(self):
        return CREDENTIAL_TYPE_LABELS.get(self.credential_type, self.credential_type)

    def status_label(self):
        return CREDENTIAL_STATUS_LABELS.get(self.status, self.status)
