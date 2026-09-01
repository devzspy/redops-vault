import os
from io import BytesIO

from flask import current_app, render_template
from sqlalchemy import func
from xhtml2pdf import pisa

from app.models.ioc import IOC
from app.models.killchain import STAGE_LABELS, KillChainEntry, stages_for_model


def build_report_context(engagement):
    stages = stages_for_model(engagement.kill_chain_model)
    entries_by_stage = {stage: [] for stage in stages}
    order_key = func.coalesce(KillChainEntry.occurred_at, KillChainEntry.created_at)
    entries = (
        KillChainEntry.query.filter_by(engagement_id=engagement.id)
        .order_by(order_key.asc())
        .all()
    )
    for entry in entries:
        entries_by_stage.setdefault(entry.stage, []).append(entry)

    ioc_order_key = func.coalesce(IOC.dropped_at, IOC.added_at)
    iocs = IOC.query.filter_by(engagement_id=engagement.id).order_by(ioc_order_key.asc()).all()

    return {
        "engagement": engagement,
        "stages": stages,
        "stage_labels": STAGE_LABELS,
        "entries_by_stage": entries_by_stage,
        "iocs": iocs,
    }


def render_report_html(engagement):
    context = build_report_context(engagement)
    return render_template("killchain/report.html", **context)


def _link_callback(uri, rel):
    """Resolve static asset URIs to real filesystem paths for xhtml2pdf,
    since it cannot follow Flask routes or fetch remote resources.
    """
    static_url = current_app.static_url_path or "/static"
    if uri.startswith(static_url):
        relative_path = uri[len(static_url):].lstrip("/")
        return os.path.join(current_app.static_folder, relative_path)
    return uri


def render_report_pdf(engagement):
    html = render_report_html(engagement)
    output = BytesIO()
    pisa_status = pisa.CreatePDF(src=html, dest=output, link_callback=_link_callback)
    if pisa_status.err:
        raise RuntimeError("Failed to generate kill chain PDF report")
    return output.getvalue()
