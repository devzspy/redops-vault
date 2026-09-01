from flask import Blueprint, Response, abort, jsonify

from app.auth_utils import current_api_user
from app.blueprints.api import serializers
from app.blueprints.api._common import json_body, parse_datetime, require_choice, require_fields, str_or_none
from app.extensions import db
from app.models.engagement import Engagement
from app.models.killchain import KillChainEntry, stages_for_model
from app.models.loot import LootFile
from app.services import activity_service, report_service

bp = Blueprint("api_killchain", __name__, url_prefix="/api/v1/engagements/<int:engagement_id>/killchain")


def _time_range_is_valid(started_at, ended_at):
    if started_at and ended_at:
        return ended_at >= started_at
    return True


def _apply_loot_ids(entry, engagement_id, data):
    if "loot_file_ids" not in data:
        return
    loot_ids = data.get("loot_file_ids") or []
    entry.loot_files = (
        LootFile.query.filter(LootFile.id.in_(loot_ids), LootFile.engagement_id == engagement_id).all()
        if loot_ids
        else []
    )


@bp.route("", methods=["GET"])
def list_entries(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return jsonify(entries=[serializers.killchain_entry_dict(e) for e in engagement.killchain_entries])


@bp.route("", methods=["POST"])
def create_entry(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    data = json_body()
    require_fields(data, "stage", "title")
    require_choice(data.get("stage"), stages_for_model(engagement.kill_chain_model), "stage")

    occurred_at = parse_datetime(data.get("occurred_at"))
    occurred_ended_at = parse_datetime(data.get("occurred_ended_at"))
    if not _time_range_is_valid(occurred_at, occurred_ended_at):
        abort(400, description="End time cannot be before start time")

    entry = KillChainEntry(
        engagement_id=engagement_id,
        stage=data["stage"],
        title=data["title"].strip(),
        description=str_or_none(data.get("description")),
        host=str_or_none(data.get("host")),
        infra_node_id=data.get("infra_node_id") or None,
        occurred_at=occurred_at,
        occurred_ended_at=occurred_ended_at,
        created_by_id=current_api_user().id,
    )
    _apply_loot_ids(entry, engagement_id, data)
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
    return jsonify(serializers.killchain_entry_dict(entry)), 201


@bp.route("/<int:entry_id>", methods=["GET"])
def get_entry(engagement_id, entry_id):
    entry = KillChainEntry.query.filter_by(id=entry_id, engagement_id=engagement_id).first_or_404()
    return jsonify(serializers.killchain_entry_dict(entry))


@bp.route("/<int:entry_id>", methods=["PATCH"])
def update_entry(engagement_id, entry_id):
    entry = KillChainEntry.query.filter_by(id=entry_id, engagement_id=engagement_id).first_or_404()
    data = json_body()

    if "stage" in data:
        require_choice(data.get("stage"), stages_for_model(entry.engagement.kill_chain_model), "stage")
        entry.stage = data["stage"]
    if "title" in data:
        title = str_or_none(data.get("title"))
        if not title:
            abort(400, description="title cannot be blank")
        entry.title = title
    if "description" in data:
        entry.description = str_or_none(data.get("description"))
    if "host" in data:
        entry.host = str_or_none(data.get("host"))
    if "infra_node_id" in data:
        entry.infra_node_id = data.get("infra_node_id") or None

    occurred_at = parse_datetime(data["occurred_at"]) if "occurred_at" in data else entry.occurred_at
    occurred_ended_at = (
        parse_datetime(data["occurred_ended_at"]) if "occurred_ended_at" in data else entry.occurred_ended_at
    )
    if not _time_range_is_valid(occurred_at, occurred_ended_at):
        abort(400, description="End time cannot be before start time")
    entry.occurred_at = occurred_at
    entry.occurred_ended_at = occurred_ended_at

    _apply_loot_ids(entry, engagement_id, data)

    activity_service.log_activity(
        engagement_id,
        "killchain_entry",
        "updated",
        f"Updated kill chain entry '{entry.title}' ({entry.stage_label()})",
        occurred_started_at=entry.occurred_at,
        occurred_ended_at=entry.occurred_ended_at,
    )
    db.session.commit()
    return jsonify(serializers.killchain_entry_dict(entry))


@bp.route("/<int:entry_id>", methods=["DELETE"])
def delete_entry(engagement_id, entry_id):
    entry = KillChainEntry.query.filter_by(id=entry_id, engagement_id=engagement_id).first_or_404()
    activity_service.log_activity(engagement_id, "killchain_entry", "deleted", f"Deleted kill chain entry '{entry.title}'")
    db.session.delete(entry)
    db.session.commit()
    return "", 204


@bp.route("/report", methods=["GET"])
def report_html(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return Response(report_service.render_report_html(engagement), mimetype="text/html")


@bp.route("/report.pdf", methods=["GET"])
def report_pdf(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    pdf_bytes = report_service.render_report_pdf(engagement)
    filename = f"killchain-report-{engagement.id}.pdf"
    response = Response(pdf_bytes, mimetype="application/pdf")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
