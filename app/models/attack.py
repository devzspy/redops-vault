from app.extensions import db

technique_tactics = db.Table(
    "technique_tactics",
    db.Column("technique_id", db.Integer, db.ForeignKey("attack_techniques.id"), primary_key=True),
    db.Column("tactic_id", db.Integer, db.ForeignKey("attack_tactics.id"), primary_key=True),
)


class AttackTactic(db.Model):
    __tablename__ = "attack_tactics"

    id = db.Column(db.Integer, primary_key=True)
    attack_id = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    short_name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    url = db.Column(db.String(500), nullable=True)

    techniques = db.relationship(
        "AttackTechnique", secondary=technique_tactics, back_populates="tactics"
    )


class AttackTechnique(db.Model):
    __tablename__ = "attack_techniques"

    id = db.Column(db.Integer, primary_key=True)
    attack_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_subtechnique = db.Column(db.Boolean, nullable=False, default=False)
    parent_technique_id = db.Column(db.Integer, db.ForeignKey("attack_techniques.id"), nullable=True)
    url = db.Column(db.String(500), nullable=True)
    last_synced_at = db.Column(db.DateTime, nullable=True)

    tactics = db.relationship(
        "AttackTactic", secondary=technique_tactics, back_populates="techniques"
    )
    sub_techniques = db.relationship(
        "AttackTechnique", backref=db.backref("parent_technique", remote_side=[id])
    )
    technique_mappings = db.relationship("TechniqueMapping", back_populates="technique")
