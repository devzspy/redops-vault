from datetime import datetime, timezone

import requests
from flask import current_app

from app.extensions import db
from app.models.attack import AttackTactic, AttackTechnique


def _external_id_and_url(stix_object):
    for ref in stix_object.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return ref.get("external_id"), ref.get("url")
    return None, None


def _is_revoked_or_deprecated(stix_object):
    return bool(stix_object.get("revoked") or stix_object.get("x_mitre_deprecated"))


def fetch_bundle():
    url = current_app.config["MITRE_ATTACK_URL"]
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def fetch_and_sync():
    """Fetch the current MITRE ATT&CK Enterprise STIX bundle and upsert
    tactics/techniques/sub-techniques into local SQLite tables. Returns a
    dict summary of counts. Safe to call repeatedly (idempotent upsert).
    """
    bundle = fetch_bundle()
    objects = bundle.get("objects", [])
    now = datetime.now(timezone.utc)

    tactic_by_shortname = {}

    tactic_count = 0
    for obj in objects:
        if obj.get("type") != "x-mitre-tactic" or _is_revoked_or_deprecated(obj):
            continue
        attack_id, url = _external_id_and_url(obj)
        if not attack_id:
            continue
        short_name = obj.get("x_mitre_shortname", "")

        tactic = AttackTactic.query.filter_by(attack_id=attack_id).first()
        if tactic is None:
            tactic = AttackTactic(attack_id=attack_id)
            db.session.add(tactic)
        tactic.name = obj.get("name", "")
        tactic.short_name = short_name
        tactic.description = obj.get("description")
        tactic.url = url
        tactic_by_shortname[short_name] = tactic
        tactic_count += 1

    db.session.flush()

    technique_by_attack_id = {}
    technique_count = 0
    for obj in objects:
        if obj.get("type") != "attack-pattern" or _is_revoked_or_deprecated(obj):
            continue
        attack_id, url = _external_id_and_url(obj)
        if not attack_id:
            continue

        technique = AttackTechnique.query.filter_by(attack_id=attack_id).first()
        if technique is None:
            technique = AttackTechnique(attack_id=attack_id)
            db.session.add(technique)
        technique.name = obj.get("name", "")
        technique.description = obj.get("description")
        technique.is_subtechnique = bool(obj.get("x_mitre_is_subtechnique"))
        technique.url = url
        technique.last_synced_at = now

        phase_shortnames = {
            phase.get("phase_name")
            for phase in obj.get("kill_chain_phases", [])
            if phase.get("kill_chain_name") == "mitre-attack"
        }
        technique.tactics = [
            tactic_by_shortname[name] for name in phase_shortnames if name in tactic_by_shortname
        ]

        technique_by_attack_id[attack_id] = technique
        technique_count += 1

    db.session.flush()

    # Sub-techniques are named "<parent_id>.<NNN>" by ATT&CK convention.
    for attack_id, technique in technique_by_attack_id.items():
        if technique.is_subtechnique and "." in attack_id:
            parent_id = attack_id.split(".")[0]
            parent = technique_by_attack_id.get(parent_id)
            technique.parent_technique_id = parent.id if parent else None

    db.session.commit()

    return {"tactics": tactic_count, "techniques": technique_count}
