from datetime import datetime

from flask import Response, abort, flash, redirect, render_template, request, url_for
from flask_jwt_extended import jwt_required

from app.auth_utils import csrf_protect, current_user
from app.blueprints.killchain import bp
from app.extensions import db
from app.models.engagement import Engagement
from app.models.infrastructure import InfrastructureNode
from app.models.killchain import STAGE_DESCRIPTIONS, STAGE_LABELS, KillChainEntry, stages_for_model
from app.models.loot import LootFile
from app.services import activity_service, report_service


def _parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


def _time_range_is_valid(started_at, ended_at):
    if started_at and ended_at:
        return ended_at >= started_at
    return True


@bp.route("/engagements/<int:engagement_id>/killchain")
@jwt_required()
def timeline(engagement_id):
    from app.models.attack import AttackTechnique

    engagement = Engagement.query.get_or_404(engagement_id)
    stages = stages_for_model(engagement.kill_chain_model)
    entries_by_stage = {stage: [] for stage in stages}
    for entry in engagement.killchain_entries:
        entries_by_stage.setdefault(entry.stage, []).append(entry)
    techniques = AttackTechnique.query.order_by(AttackTechnique.attack_id.asc()).all()
    return render_template(
        "killchain/timeline.html",
        engagement=engagement,
        stages=stages,
        stage_labels=STAGE_LABELS,
        stage_descriptions=STAGE_DESCRIPTIONS,
        entries_by_stage=entries_by_stage,
        techniques=techniques,
    )


@bp.route("/engagements/<int:engagement_id>/killchain/new")
@jwt_required()
def new_entry_form(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    files = LootFile.query.filter_by(engagement_id=engagement_id).all()
    nodes = InfrastructureNode.query.filter_by(engagement_id=engagement_id).order_by(InfrastructureNode.name.asc()).all()
    return render_template(
        "killchain/entry_form.html",
        engagement=engagement,
        entry=None,
        stages=stages_for_model(engagement.kill_chain_model),
        stage_labels=STAGE_LABELS,
        files=files,
        nodes=nodes,
    )


@bp.route("/engagements/<int:engagement_id>/killchain", methods=["POST"])
@csrf_protect
def create_entry(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)

    stage = request.form.get("stage")
    title = request.form.get("title", "").strip()
    if stage not in stages_for_model(engagement.kill_chain_model) or not title:
        flash("Stage and title are required.", "danger")
        return redirect(url_for("killchain.new_entry_form", engagement_id=engagement_id))

    occurred_at = _parse_datetime(request.form.get("occurred_at"))
    occurred_ended_at = _parse_datetime(request.form.get("occurred_ended_at"))
    if not _time_range_is_valid(occurred_at, occurred_ended_at):
        flash("End time cannot be before start time.", "danger")
        return redirect(url_for("killchain.new_entry_form", engagement_id=engagement_id))

    entry = KillChainEntry(
        engagement_id=engagement_id,
        stage=stage,
        title=title,
        description=request.form.get("description", "").strip() or None,
        host=request.form.get("host", "").strip() or None,
        infra_node_id=request.form.get("infra_node_id", type=int) or None,
        occurred_at=occurred_at,
        occurred_ended_at=occurred_ended_at,
        created_by_id=int(current_user().id),
    )

    loot_ids = request.form.getlist("loot_file_ids")
    if loot_ids:
        entry.loot_files = (
            LootFile.query.filter(LootFile.id.in_(loot_ids), LootFile.engagement_id == engagement_id)
            .all()
        )

    db.session.add(entry)
    db.session.flush()
    activity_service.log_activity(
        engagement_id,
        "killchain_entry",
        "created",
        f"Added kill chain entry '{entry.title}' ({entry.stage_label()})",
        occurred_started_at=entry.occurred_at,
        occurred_ended_at=entry.occurred_ended_at,
    )
    db.session.commit()
    flash("Kill chain entry added.", "success")
    return redirect(url_for("killchain.timeline", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/killchain/<int:entry_id>/edit")
@jwt_required()
def edit_entry_form(engagement_id, entry_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    entry = KillChainEntry.query.filter_by(id=entry_id, engagement_id=engagement_id).first_or_404()
    files = LootFile.query.filter_by(engagement_id=engagement_id).all()
    nodes = InfrastructureNode.query.filter_by(engagement_id=engagement_id).order_by(InfrastructureNode.name.asc()).all()
    return render_template(
        "killchain/entry_form.html",
        engagement=engagement,
        entry=entry,
        stages=stages_for_model(engagement.kill_chain_model),
        stage_labels=STAGE_LABELS,
        files=files,
        nodes=nodes,
    )


@bp.route("/engagements/<int:engagement_id>/killchain/<int:entry_id>/edit", methods=["POST"])
@csrf_protect
def edit_entry(engagement_id, entry_id):
    entry = KillChainEntry.query.filter_by(id=entry_id, engagement_id=engagement_id).first_or_404()

    stage = request.form.get("stage")
    title = request.form.get("title", "").strip()
    if stage not in stages_for_model(entry.engagement.kill_chain_model) or not title:
        abort(400, description="Stage and title are required")

    occurred_at = _parse_datetime(request.form.get("occurred_at"))
    occurred_ended_at = _parse_datetime(request.form.get("occurred_ended_at"))
    if not _time_range_is_valid(occurred_at, occurred_ended_at):
        abort(400, description="End time cannot be before start time")

    entry.stage = stage
    entry.title = title
    entry.description = request.form.get("description", "").strip() or None
    entry.host = request.form.get("host", "").strip() or None
    entry.infra_node_id = request.form.get("infra_node_id", type=int) or None
    entry.occurred_at = occurred_at
    entry.occurred_ended_at = occurred_ended_at

    loot_ids = request.form.getlist("loot_file_ids")
    entry.loot_files = (
        LootFile.query.filter(LootFile.id.in_(loot_ids), LootFile.engagement_id == engagement_id).all()
        if loot_ids
        else []
    )

    activity_service.log_activity(
        engagement_id,
        "killchain_entry",
        "updated",
        f"Updated kill chain entry '{entry.title}' ({entry.stage_label()})",
        occurred_started_at=entry.occurred_at,
        occurred_ended_at=entry.occurred_ended_at,
    )
    db.session.commit()
    flash("Kill chain entry updated.", "success")
    return redirect(url_for("killchain.timeline", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/killchain/<int:entry_id>/delete", methods=["POST"])
@csrf_protect
def delete_entry(engagement_id, entry_id):
    entry = KillChainEntry.query.filter_by(id=entry_id, engagement_id=engagement_id).first_or_404()
    activity_service.log_activity(
        engagement_id, "killchain_entry", "deleted", f"Deleted kill chain entry '{entry.title}'"
    )
    db.session.delete(entry)
    db.session.commit()
    flash("Kill chain entry deleted.", "success")
    return redirect(url_for("killchain.timeline", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/killchain/report")
@jwt_required()
def report_html(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    html = report_service.render_report_html(engagement)
    return html


@bp.route("/engagements/<int:engagement_id>/killchain/report.pdf")
@jwt_required()
def report_pdf(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    pdf_bytes = report_service.render_report_pdf(engagement)
    filename = f"killchain-report-{engagement.id}.pdf"
    response = Response(pdf_bytes, mimetype="application/pdf")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
