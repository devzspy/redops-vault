from datetime import datetime, timezone

from app.models.finding import Finding
from app.models.infrastructure import InfrastructureNode
from app.models.ioc import IOC
from app.models.killchain import KillChainEntry
from app.models.loot import Credential, LootFile
from app.services.sanitize_service import html_to_markdown


def sorted_findings(engagement):
    findings = Finding.query.filter_by(engagement_id=engagement.id).all()
    return sorted(findings, key=lambda f: (f.severity_rank(), f.title.lower()))


def apply_correlations(finding, engagement_id, data):
    """Sets finding's cross-linked collections (loot files, infra nodes,
    credentials, IOCs, killchain entries) from id lists in `data` (a plain
    dict of field name -> list of ids, e.g. request.form with getlist
    already applied, or a JSON body's arrays). Ids not belonging to
    `engagement_id` are silently dropped. A missing/empty key clears that
    collection, matching the HTML form's full-overwrite semantics.
    """

    def _linked(model, field_name):
        ids = data.get(field_name) or []
        if not ids:
            return []
        return model.query.filter(model.id.in_(ids), model.engagement_id == engagement_id).all()

    finding.loot_files = _linked(LootFile, "loot_file_ids")
    finding.infra_nodes = _linked(InfrastructureNode, "infra_node_ids")
    finding.credentials = _linked(Credential, "credential_ids")
    finding.iocs = _linked(IOC, "ioc_ids")
    finding.killchain_entries = _linked(KillChainEntry, "killchain_entry_ids")


def render_markdown_report(engagement):
    """Renders all of an engagement's findings as a single portable Markdown
    document — plain headers, bold/italic, links, lists, and images, no
    HTML-in-markdown and no GFM-only extensions, so it pastes cleanly into
    Confluence, SharePoint, or any other system's markdown importer.
    """
    findings = sorted_findings(engagement)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [
        f"# Findings Report — {engagement.name}",
        "",
        f"**Client:** {engagement.client_name}",
        f"**Status:** {engagement.status}",
        f"**Generated:** {generated}",
        "",
        "---",
        "",
    ]

    if not findings:
        lines.append("_No findings recorded yet._")
    else:
        for finding in findings:
            severity_label = finding.severity_label()
            lines.append(f"## [{severity_label.upper()}] {finding.title}")
            lines.append("")
            lines.append(f"**Severity:** {severity_label}")
            lines.append("")
            lines.append("### Details")
            lines.append("")
            lines.append(html_to_markdown(finding.details) or "_No details provided._")
            if finding.infra_nodes:
                lines.append("")
                names = ", ".join(n.name for n in finding.infra_nodes)
                lines.append(f"**Affected hosts:** {names}")
            if finding.loot_files:
                lines.append("")
                names = ", ".join(f.original_filename for f in finding.loot_files)
                lines.append(f"**Attached evidence:** {names}")
            if finding.credentials:
                lines.append("")
                names = ", ".join(c.display_label() for c in finding.credentials)
                lines.append(f"**Related credentials:** {names}")
            if finding.iocs:
                lines.append("")
                names = ", ".join(i.display_label() for i in finding.iocs)
                lines.append(f"**Related IOCs:** {names}")
            if finding.killchain_entries:
                lines.append("")
                names = ", ".join(f"{e.stage_label()} — {e.title}" for e in finding.killchain_entries)
                lines.append(f"**Related kill chain entries:** {names}")
            lines.append("")
            lines.append("### Remediation")
            lines.append("")
            lines.append(html_to_markdown(finding.remediation) or "_No remediation provided._")
            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
