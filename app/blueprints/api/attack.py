from flask import Blueprint, abort, jsonify

from app.auth_utils import current_api_user
from app.blueprints.api import serializers
from app.blueprints.api._common import json_body, str_or_none
from app.extensions import db
from app.models.attack import AttackTechnique
from app.models.killchain import KillChainEntry, TechniqueMapping
from app.models.loot import LootFile
from app.models.user import ROLE_ADMIN
from app.services import activity_service, attack_service, attack_sync

bp = Blueprint("api_attack", __name__)


@bp.route("/api/v1/attack/tactics", methods=["GET"])
def list_tactics():
    tactics = attack_service.build_matrix_tactics()
    return jsonify(tactics=[serializers.attack_tactic_dict(t) for t in tactics])


@bp.route("/api/v1/attack/techniques/<string:attack_id>", methods=["GET"])
def get_technique(attack_id):
    technique = AttackTechnique.query.filter_by(attack_id=attack_id).first_or_404()
    mappings = TechniqueMapping.query.filter_by(technique_id=technique.id).all()
    data = serializers.attack_technique_dict(technique)
    data["mappings"] = [serializers.technique_mapping_dict(m) for m in mappings]
    return jsonify(data)


@bp.route("/api/v1/attack/refresh", methods=["POST"])
def refresh():
    if current_api_user().role != ROLE_ADMIN:
        abort(403, description="Admin role required")
    try:
        summary = attack_sync.fetch_and_sync()
    except Exception as exc:
        abort(502, description=f"Failed to refresh ATT&CK data: {exc}")
    return jsonify(summary)


def _create_mapping(engagement_id, technique_attack_id, target_label, notes, loot_file_id=None, killchain_entry_id=None):
    technique = AttackTechnique.query.filter_by(attack_id=technique_attack_id).first()
    if technique is None:
        abort(400, description="Unknown ATT&CK technique")

    mapping = TechniqueMapping(
        engagement_id=engagement_id,
        technique_id=technique.id,
        loot_file_id=loot_file_id,
        killchain_entry_id=killchain_entry_id,
        mapped_by_id=current_api_user().id,
        notes=notes,
    )
    db.session.add(mapping)
    activity_service.log_activity(
        engagement_id,
        "technique_mapping",
        "mapped",
        f"Mapped technique {technique.attack_id} ({technique.name}) to {target_label}",
    )
    db.session.commit()
    return mapping


@bp.route("/api/v1/engagements/<int:engagement_id>/loot/<int:file_id>/map-technique", methods=["POST"])
def map_technique_to_loot(engagement_id, file_id):
    loot_file = LootFile.query.filter_by(id=file_id, engagement_id=engagement_id).first_or_404()
    data = json_body()
    mapping = _create_mapping(
        engagement_id,
        (data.get("attack_id") or "").strip(),
        f"loot file '{loot_file.original_filename}'",
        str_or_none(data.get("notes")),
        loot_file_id=loot_file.id,
    )
    return jsonify(serializers.technique_mapping_dict(mapping)), 201


@bp.route("/api/v1/engagements/<int:engagement_id>/killchain/<int:entry_id>/map-technique", methods=["POST"])
def map_technique_to_killchain(engagement_id, entry_id):
    entry = KillChainEntry.query.filter_by(id=entry_id, engagement_id=engagement_id).first_or_404()
    data = json_body()
    mapping = _create_mapping(
        engagement_id,
        (data.get("attack_id") or "").strip(),
        f"kill chain entry '{entry.title}'",
        str_or_none(data.get("notes")),
        killchain_entry_id=entry.id,
    )
    return jsonify(serializers.technique_mapping_dict(mapping)), 201


@bp.route("/api/v1/technique-mappings/<int:mapping_id>", methods=["DELETE"])
def delete_mapping(mapping_id):
    mapping = TechniqueMapping.query.get_or_404(mapping_id)
    engagement_id = mapping.engagement_id
    if mapping.loot_file_id:
        target_label = f"loot file '{mapping.loot_file.original_filename}'"
    else:
        target_label = f"kill chain entry '{mapping.killchain_entry.title}'"
    activity_service.log_activity(
        engagement_id,
        "technique_mapping",
        "unmapped",
        f"Removed technique {mapping.technique.attack_id} mapping from {target_label}",
    )
    db.session.delete(mapping)
    db.session.commit()
    return "", 204
