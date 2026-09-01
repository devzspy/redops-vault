from urllib.parse import quote

from flask import Response, flash, redirect, render_template, request, url_for
from flask_jwt_extended import jwt_required

from app.auth_utils import csrf_protect, current_user
from app.blueprints.findings import bp
from app.extensions import db
from app.models.engagement import Engagement
from app.models.finding import SEVERITIES, Finding
from app.models.infrastructure import InfrastructureNode
from app.models.ioc import IOC
from app.models.killchain import KillChainEntry
from app.models.loot import Credential, LootFile
from app.services import activity_service, findings_service
from app.services.sanitize_service import clean_html


def _engagement_loot(engagement_id):
    return LootFile.query.filter_by(engagement_id=engagement_id).order_by(LootFile.original_filename.asc()).all()


def _engagement_nodes(engagement_id):
    return (
        InfrastructureNode.query.filter_by(engagement_id=engagement_id)
        .order_by(InfrastructureNode.name.asc())
        .all()
    )


def _engagement_credentials(engagement_id):
    return (
        Credential.query.filter_by(engagement_id=engagement_id)
        .order_by(Credential.username.asc())
        .all()
    )


def _engagement_iocs(engagement_id):
    return IOC.query.filter_by(engagement_id=engagement_id).order_by(IOC.added_at.desc()).all()


def _engagement_killchain_entries(engagement_id):
    return (
        KillChainEntry.query.filter_by(engagement_id=engagement_id)
        .order_by(KillChainEntry.created_at.asc())
        .all()
    )


def _correlation_form_data():
    return {
        "loot_file_ids": request.form.getlist("loot_file_ids"),
        "infra_node_ids": request.form.getlist("infra_node_ids"),
        "credential_ids": request.form.getlist("credential_ids"),
        "ioc_ids": request.form.getlist("ioc_ids"),
        "killchain_entry_ids": request.form.getlist("killchain_entry_ids"),
    }


def _correlation_context(engagement_id):
    return {
        "files": _engagement_loot(engagement_id),
        "nodes": _engagement_nodes(engagement_id),
        "credentials": _engagement_credentials(engagement_id),
        "iocs": _engagement_iocs(engagement_id),
        "killchain_entries": _engagement_killchain_entries(engagement_id),
    }


@bp.route("/engagements/<int:engagement_id>/findings")
@jwt_required()
def list_findings(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    findings = findings_service.sorted_findings(engagement)
    return render_template("findings/list.html", engagement=engagement, findings=findings)


@bp.route("/engagements/<int:engagement_id>/findings/new")
@jwt_required()
def new_finding_form(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return render_template(
        "findings/form.html",
        engagement=engagement,
        finding=None,
        severities=SEVERITIES,
        **_correlation_context(engagement_id),
    )


@bp.route("/engagements/<int:engagement_id>/findings", methods=["POST"])
@csrf_protect
def create_finding(engagement_id):
    Engagement.query.get_or_404(engagement_id)

    title = request.form.get("title", "").strip()
    severity = request.form.get("severity")
    if not title or severity not in SEVERITIES:
        flash("Title and a valid severity are required.", "danger")
        return redirect(url_for("findings.new_finding_form", engagement_id=engagement_id))

    finding = Finding(
        engagement_id=engagement_id,
        title=title,
        severity=severity,
        details=clean_html(request.form.get("details", "")),
        remediation=clean_html(request.form.get("remediation", "")),
        created_by_id=int(current_user().id),
    )
    db.session.add(finding)
    findings_service.apply_correlations(finding, engagement_id, _correlation_form_data())
    db.session.flush()
    activity_service.log_activity(
        engagement_id,
        "finding",
        "created",
        f"Added finding '{finding.title}' ({finding.severity_label()})",
    )
    db.session.commit()
    flash("Finding added.", "success")
    return redirect(url_for("findings.list_findings", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/findings/<int:finding_id>/edit")
@jwt_required()
def edit_finding_form(engagement_id, finding_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    finding = Finding.query.filter_by(id=finding_id, engagement_id=engagement_id).first_or_404()
    return render_template(
        "findings/form.html",
        engagement=engagement,
        finding=finding,
        severities=SEVERITIES,
        **_correlation_context(engagement_id),
    )


@bp.route("/engagements/<int:engagement_id>/findings/<int:finding_id>/edit", methods=["POST"])
@csrf_protect
def edit_finding(engagement_id, finding_id):
    finding = Finding.query.filter_by(id=finding_id, engagement_id=engagement_id).first_or_404()

    title = request.form.get("title", "").strip()
    severity = request.form.get("severity")
    if not title or severity not in SEVERITIES:
        flash("Title and a valid severity are required.", "danger")
        return redirect(url_for("findings.edit_finding_form", engagement_id=engagement_id, finding_id=finding_id))

    finding.title = title
    finding.severity = severity
    finding.details = clean_html(request.form.get("details", ""))
    finding.remediation = clean_html(request.form.get("remediation", ""))
    findings_service.apply_correlations(finding, engagement_id, _correlation_form_data())
    activity_service.log_activity(
        engagement_id,
        "finding",
        "updated",
        f"Updated finding '{finding.title}' ({finding.severity_label()})",
    )
    db.session.commit()
    flash("Finding updated.", "success")
    return redirect(url_for("findings.list_findings", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/findings/<int:finding_id>/delete", methods=["POST"])
@csrf_protect
def delete_finding(engagement_id, finding_id):
    finding = Finding.query.filter_by(id=finding_id, engagement_id=engagement_id).first_or_404()
    activity_service.log_activity(engagement_id, "finding", "deleted", f"Deleted finding '{finding.title}'")
    db.session.delete(finding)
    db.session.commit()
    flash("Finding deleted.", "success")
    return redirect(url_for("findings.list_findings", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/findings/report.md")
@jwt_required()
def export_markdown(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    markdown = findings_service.render_markdown_report(engagement)
    safe_name = engagement.name.replace('"', "").replace("/", "-")
    ascii_name = safe_name.encode("ascii", "ignore").decode("ascii").strip() or "report"
    response = Response(markdown, mimetype="text/markdown")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="findings-{ascii_name}.md"; '
        f"filename*=UTF-8''{quote(f'findings-{safe_name}.md')}"
    )
    return response
