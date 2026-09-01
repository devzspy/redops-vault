from datetime import datetime, timezone

from app.extensions import db

KILL_CHAIN_MODEL_LMCKC = "lmckc"
KILL_CHAIN_MODEL_UKC = "ukc"
KILL_CHAIN_MODELS = (KILL_CHAIN_MODEL_LMCKC, KILL_CHAIN_MODEL_UKC)
KILL_CHAIN_MODEL_LABELS = {
    KILL_CHAIN_MODEL_LMCKC: "Lockheed Martin Cyber Kill Chain",
    KILL_CHAIN_MODEL_UKC: "Unified Kill Chain",
}

STAGE_RECONNAISSANCE = "reconnaissance"
STAGE_WEAPONIZATION = "weaponization"
STAGE_DELIVERY = "delivery"
STAGE_EXPLOITATION = "exploitation"
STAGE_INSTALLATION = "installation"
STAGE_COMMAND_AND_CONTROL = "command_and_control"
STAGE_ACTIONS_ON_OBJECTIVES = "actions_on_objectives"

STAGE_SOCIAL_ENGINEERING = "social_engineering"
STAGE_PERSISTENCE = "persistence"
STAGE_DEFENSE_EVASION = "defense_evasion"
STAGE_PIVOTING = "pivoting"
STAGE_DISCOVERY = "discovery"
STAGE_PRIVILEGE_ESCALATION = "privilege_escalation"
STAGE_EXECUTION = "execution"
STAGE_CREDENTIAL_ACCESS = "credential_access"
STAGE_LATERAL_MOVEMENT = "lateral_movement"
STAGE_COLLECTION = "collection"
STAGE_EXFILTRATION = "exfiltration"
STAGE_IMPACT = "impact"
STAGE_OBJECTIVES = "objectives"

STAGES_LMCKC = (
    STAGE_RECONNAISSANCE,
    STAGE_WEAPONIZATION,
    STAGE_DELIVERY,
    STAGE_EXPLOITATION,
    STAGE_INSTALLATION,
    STAGE_COMMAND_AND_CONTROL,
    STAGE_ACTIONS_ON_OBJECTIVES,
)

STAGES_UKC = (
    STAGE_RECONNAISSANCE,
    STAGE_WEAPONIZATION,
    STAGE_DELIVERY,
    STAGE_SOCIAL_ENGINEERING,
    STAGE_EXPLOITATION,
    STAGE_PERSISTENCE,
    STAGE_DEFENSE_EVASION,
    STAGE_COMMAND_AND_CONTROL,
    STAGE_PIVOTING,
    STAGE_DISCOVERY,
    STAGE_PRIVILEGE_ESCALATION,
    STAGE_EXECUTION,
    STAGE_CREDENTIAL_ACCESS,
    STAGE_LATERAL_MOVEMENT,
    STAGE_COLLECTION,
    STAGE_EXFILTRATION,
    STAGE_IMPACT,
    STAGE_OBJECTIVES,
)

STAGES_BY_MODEL = {
    KILL_CHAIN_MODEL_LMCKC: STAGES_LMCKC,
    KILL_CHAIN_MODEL_UKC: STAGES_UKC,
}


def stages_for_model(kill_chain_model):
    """Ordered stage slugs for a kill chain model, falling back to the
    Lockheed Martin model for an unrecognized/legacy value.
    """
    return STAGES_BY_MODEL.get(kill_chain_model, STAGES_LMCKC)


# Keyed by stage slug rather than by model, since several slugs (e.g.
# reconnaissance) are shared verbatim between models.
STAGE_LABELS = {
    STAGE_RECONNAISSANCE: "Reconnaissance",
    STAGE_WEAPONIZATION: "Weaponization",
    STAGE_DELIVERY: "Delivery",
    STAGE_SOCIAL_ENGINEERING: "Social Engineering",
    STAGE_EXPLOITATION: "Exploitation",
    STAGE_PERSISTENCE: "Persistence",
    STAGE_DEFENSE_EVASION: "Defense Evasion",
    STAGE_INSTALLATION: "Installation",
    STAGE_COMMAND_AND_CONTROL: "Command & Control",
    STAGE_PIVOTING: "Pivoting",
    STAGE_DISCOVERY: "Discovery",
    STAGE_PRIVILEGE_ESCALATION: "Privilege Escalation",
    STAGE_EXECUTION: "Execution",
    STAGE_CREDENTIAL_ACCESS: "Credential Access",
    STAGE_LATERAL_MOVEMENT: "Lateral Movement",
    STAGE_COLLECTION: "Collection",
    STAGE_EXFILTRATION: "Exfiltration",
    STAGE_IMPACT: "Impact",
    STAGE_OBJECTIVES: "Objectives",
    STAGE_ACTIONS_ON_OBJECTIVES: "Actions on Objectives",
}

STAGE_DESCRIPTIONS = {
    STAGE_RECONNAISSANCE: "Harvesting information about the target — emails, social media, network details — to plan the attack.",
    STAGE_WEAPONIZATION: "Coupling an exploit with a payload, such as a backdoor, into a deliverable artifact.",
    STAGE_DELIVERY: "Transmitting the weaponized artifact to the target, e.g. via email, a website, or removable media.",
    STAGE_SOCIAL_ENGINEERING: "Manipulating a person into taking an action or divulging information that aids the attack.",
    STAGE_EXPLOITATION: "Triggering the exploit to execute attacker code on the target's system.",
    STAGE_PERSISTENCE: "Maintaining a foothold on the target across restarts, credential changes, or other interruptions.",
    STAGE_DEFENSE_EVASION: "Avoiding detection by security controls, logging, and defenders.",
    STAGE_INSTALLATION: "Installing persistent malware or a backdoor on the target to maintain access.",
    STAGE_COMMAND_AND_CONTROL: "Establishing a channel for remote, hands-on-keyboard control of the target.",
    STAGE_PIVOTING: "Using a compromised system as a relay to reach other parts of the network.",
    STAGE_DISCOVERY: "Enumerating the target environment to understand its systems, users, and defenses.",
    STAGE_PRIVILEGE_ESCALATION: "Gaining higher-level permissions on a system or within the environment.",
    STAGE_EXECUTION: "Running attacker-controlled code on a target system.",
    STAGE_CREDENTIAL_ACCESS: "Stealing account names, passwords, or other credentials.",
    STAGE_LATERAL_MOVEMENT: "Moving from one compromised system to another within the target environment.",
    STAGE_COLLECTION: "Gathering data of interest ahead of exfiltration.",
    STAGE_EXFILTRATION: "Removing collected data from the target environment.",
    STAGE_IMPACT: "Manipulating, interrupting, or destroying systems and data.",
    STAGE_OBJECTIVES: "Achieving the attacker's ultimate goal for the engagement.",
    STAGE_ACTIONS_ON_OBJECTIVES: "Carrying out the attacker's ultimate goal — data exfiltration, destruction, or lateral movement.",
}

killchain_entry_loot = db.Table(
    "killchain_entry_loot",
    db.Column("entry_id", db.Integer, db.ForeignKey("killchain_entries.id"), primary_key=True),
    db.Column("loot_file_id", db.Integer, db.ForeignKey("loot_files.id"), primary_key=True),
)


class KillChainEntry(db.Model):
    __tablename__ = "killchain_entries"

    id = db.Column(db.Integer, primary_key=True)
    engagement_id = db.Column(db.Integer, db.ForeignKey("engagements.id"), nullable=False, index=True)
    stage = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    host = db.Column(db.String(255), nullable=True)
    infra_node_id = db.Column(
        db.Integer, db.ForeignKey("infrastructure_nodes.id", ondelete="SET NULL"), nullable=True
    )
    # occurred_at is the start of the activity (kept as the original name for
    # backward compatibility); occurred_ended_at is optional for anything
    # with a duration, e.g. an nmap scan.
    occurred_at = db.Column(db.DateTime, nullable=True)
    occurred_ended_at = db.Column(db.DateTime, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    engagement = db.relationship("Engagement", back_populates="killchain_entries")
    created_by = db.relationship("User")
    infra_node = db.relationship("InfrastructureNode")
    loot_files = db.relationship("LootFile", secondary=killchain_entry_loot)
    technique_mappings = db.relationship(
        "TechniqueMapping", back_populates="killchain_entry", cascade="all, delete-orphan"
    )

    def stage_label(self):
        return STAGE_LABELS.get(self.stage, self.stage)

    def occurred_range_label(self):
        if not self.occurred_at:
            return None
        if not self.occurred_ended_at:
            return self.occurred_at.strftime("%Y-%m-%d %H:%M")
        if self.occurred_at.date() == self.occurred_ended_at.date():
            return (
                f"{self.occurred_at.strftime('%Y-%m-%d %H:%M')}"
                f" – {self.occurred_ended_at.strftime('%H:%M')}"
            )
        return (
            f"{self.occurred_at.strftime('%Y-%m-%d %H:%M')}"
            f" – {self.occurred_ended_at.strftime('%Y-%m-%d %H:%M')}"
        )


class TechniqueMapping(db.Model):
    __tablename__ = "technique_mappings"
    __table_args__ = (
        db.CheckConstraint(
            "(loot_file_id IS NOT NULL AND killchain_entry_id IS NULL) OR "
            "(loot_file_id IS NULL AND killchain_entry_id IS NOT NULL)",
            name="ck_technique_mapping_single_target",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    engagement_id = db.Column(db.Integer, db.ForeignKey("engagements.id"), nullable=False, index=True)
    technique_id = db.Column(db.Integer, db.ForeignKey("attack_techniques.id"), nullable=False)
    loot_file_id = db.Column(db.Integer, db.ForeignKey("loot_files.id"), nullable=True)
    killchain_entry_id = db.Column(db.Integer, db.ForeignKey("killchain_entries.id"), nullable=True)
    mapped_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    mapped_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    notes = db.Column(db.Text, nullable=True)

    engagement = db.relationship("Engagement")
    technique = db.relationship("AttackTechnique", back_populates="technique_mappings")
    loot_file = db.relationship("LootFile", back_populates="technique_mappings")
    killchain_entry = db.relationship("KillChainEntry", back_populates="technique_mappings")
    mapped_by = db.relationship("User")
