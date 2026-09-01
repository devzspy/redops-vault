from flask import abort, flash, redirect, render_template, request, url_for
from flask_jwt_extended import jwt_required

from app.auth_utils import csrf_protect, current_user, role_required_csrf
from app.blueprints.attack import bp
from app.extensions import db
from app.models.attack import AttackTactic, AttackTechnique
from app.models.engagement import Engagement
from app.models.killchain import KillChainEntry, TechniqueMapping
from app.models.loot import LootFile
from app.services import activity_service, attack_service, attack_sync


@bp.route("/attack")
@jwt_required()
def browse():
    tactics = attack_service.build_matrix_tactics()
    return render_template("attack/browse.html", tactics=tactics)


@bp.route("/attack/techniques/<string:attack_id>")
@jwt_required()
def technique_detail(attack_id):
    technique = AttackTechnique.query.filter_by(attack_id=attack_id).first_or_404()
    mappings = TechniqueMapping.query.filter_by(technique_id=technique.id).all()
    return render_template("attack/technique_detail.html", technique=technique, mappings=mappings)


@bp.route("/attack/refresh", methods=["POST"])
@role_required_csrf("admin")
def refresh():
    try:
        summary = attack_sync.fetch_and_sync()
        flash(
            f"ATT&CK data refreshed: {summary['tactics']} tactics, "
            f"{summary['techniques']} techniques.",
            "success",
        )
    except Exception as exc:
        flash(f"Failed to refresh ATT&CK data: {exc}", "danger")
    return redirect(url_for("attack.browse"))


def _create_mapping(engagement_id, technique_attack_id, target_label, loot_file_id=None, killchain_entry_id=None):
    technique = AttackTechnique.query.filter_by(attack_id=technique_attack_id).first()
    if technique is None:
        abort(400, description="Unknown ATT&CK technique")

    mapping = TechniqueMapping(
        engagement_id=engagement_id,
        technique_id=technique.id,
        loot_file_id=loot_file_id,
        killchain_entry_id=killchain_entry_id,
        mapped_by_id=int(current_user().id),
        notes=request.form.get("notes", "").strip() or None,
    )
    db.session.add(mapping)
    activity_service.log_activity(
        engagement_id,
        "technique_mapping",
        "mapped",
        f"Mapped technique {technique.attack_id} ({technique.name}) to {target_label}",
    )
    db.session.commit()


@bp.route("/engagements/<int:engagement_id>/loot/<int:file_id>/map-technique", methods=["POST"])
@csrf_protect
def map_technique_to_loot(engagement_id, file_id):
    loot_file = LootFile.query.filter_by(id=file_id, engagement_id=engagement_id).first_or_404()
    attack_id = request.form.get("attack_id", "").strip()
    _create_mapping(
        engagement_id, attack_id, f"loot file '{loot_file.original_filename}'", loot_file_id=loot_file.id
    )
    flash("Technique mapped.", "success")
    return redirect(url_for("loot.file_detail", engagement_id=engagement_id, file_id=file_id))


@bp.route(
    "/engagements/<int:engagement_id>/killchain/<int:entry_id>/map-technique", methods=["POST"]
)
@csrf_protect
def map_technique_to_killchain(engagement_id, entry_id):
    entry = KillChainEntry.query.filter_by(id=entry_id, engagement_id=engagement_id).first_or_404()
    attack_id = request.form.get("attack_id", "").strip()
    _create_mapping(
        engagement_id, attack_id, f"kill chain entry '{entry.title}'", killchain_entry_id=entry.id
    )
    flash("Technique mapped.", "success")
    return redirect(url_for("killchain.timeline", engagement_id=engagement_id))


@bp.route("/technique-mappings/<int:mapping_id>/delete", methods=["POST"])
@csrf_protect
def delete_mapping(mapping_id):
    mapping = TechniqueMapping.query.get_or_404(mapping_id)
    engagement_id = mapping.engagement_id
    if mapping.loot_file_id:
        redirect_target = url_for(
            "loot.file_detail", engagement_id=engagement_id, file_id=mapping.loot_file_id
        )
        target_label = f"loot file '{mapping.loot_file.original_filename}'"
    else:
        redirect_target = url_for("killchain.timeline", engagement_id=engagement_id)
        target_label = f"kill chain entry '{mapping.killchain_entry.title}'"
    activity_service.log_activity(
        engagement_id,
        "technique_mapping",
        "unmapped",
        f"Removed technique {mapping.technique.attack_id} mapping from {target_label}",
    )
    db.session.delete(mapping)
    db.session.commit()
    flash("Technique mapping removed.", "success")
    return redirect(redirect_target)
