from flask import Blueprint, Response, abort, jsonify

from app.auth_utils import current_api_user
from app.blueprints.api import serializers
from app.blueprints.api._common import json_body, require_choice, require_fields, str_or_none
from app.extensions import db
from app.models.engagement import Engagement
from app.models.finding import SEVERITIES, Finding
from app.services import activity_service, findings_service
from app.services.sanitize_service import clean_html

bp = Blueprint("api_findings", __name__, url_prefix="/api/v1/engagements/<int:engagement_id>/findings")


@bp.route("", methods=["GET"])
def list_findings(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    findings = findings_service.sorted_findings(engagement)
    return jsonify(findings=[serializers.finding_dict(f) for f in findings])


@bp.route("", methods=["POST"])
def create_finding(engagement_id):
    Engagement.query.get_or_404(engagement_id)
    data = json_body()
    require_fields(data, "title", "severity")
    require_choice(data.get("severity"), SEVERITIES, "severity")

    finding = Finding(
        engagement_id=engagement_id,
        title=data["title"].strip(),
        severity=data["severity"],
        details=clean_html(data.get("details", "")),
        remediation=clean_html(data.get("remediation", "")),
        created_by_id=current_api_user().id,
    )
    db.session.add(finding)
    findings_service.apply_correlations(finding, engagement_id, data)
    db.session.flush()
    activity_service.log_activity(
        engagement_id, "finding", "created", f"Added finding '{finding.title}' ({finding.severity_label()})"
    )
    db.session.commit()
    return jsonify(serializers.finding_dict(finding)), 201


@bp.route("/<int:finding_id>", methods=["GET"])
def get_finding(engagement_id, finding_id):
    finding = Finding.query.filter_by(id=finding_id, engagement_id=engagement_id).first_or_404()
    return jsonify(serializers.finding_dict(finding))


@bp.route("/<int:finding_id>", methods=["PATCH"])
def update_finding(engagement_id, finding_id):
    finding = Finding.query.filter_by(id=finding_id, engagement_id=engagement_id).first_or_404()
    data = json_body()

    if "title" in data:
        title = str_or_none(data.get("title"))
        if not title:
            abort(400, description="title cannot be blank")
        finding.title = title
    if "severity" in data:
        require_choice(data.get("severity"), SEVERITIES, "severity")
        finding.severity = data["severity"]
    if "details" in data:
        finding.details = clean_html(data.get("details", ""))
    if "remediation" in data:
        finding.remediation = clean_html(data.get("remediation", ""))
    if any(k in data for k in ("loot_file_ids", "infra_node_ids", "credential_ids", "ioc_ids", "killchain_entry_ids")):
        findings_service.apply_correlations(finding, engagement_id, data)

    activity_service.log_activity(
        engagement_id, "finding", "updated", f"Updated finding '{finding.title}' ({finding.severity_label()})"
    )
    db.session.commit()
    return jsonify(serializers.finding_dict(finding))


@bp.route("/<int:finding_id>", methods=["DELETE"])
def delete_finding(engagement_id, finding_id):
    finding = Finding.query.filter_by(id=finding_id, engagement_id=engagement_id).first_or_404()
    activity_service.log_activity(engagement_id, "finding", "deleted", f"Deleted finding '{finding.title}'")
    db.session.delete(finding)
    db.session.commit()
    return "", 204


@bp.route("/report.md", methods=["GET"])
def export_markdown(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    markdown = findings_service.render_markdown_report(engagement)
    return Response(markdown, mimetype="text/markdown")
