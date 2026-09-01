from typing import List, Optional

from mcp_server import client


def _correlation_payload(loot_file_ids, infra_node_ids, credential_ids, ioc_ids, killchain_entry_ids):
    return {
        k: v
        for k, v in {
            "loot_file_ids": loot_file_ids,
            "infra_node_ids": infra_node_ids,
            "credential_ids": credential_ids,
            "ioc_ids": ioc_ids,
            "killchain_entry_ids": killchain_entry_ids,
        }.items()
        if v is not None
    }


def register(mcp):
    @mcp.tool()
    def finding_list(engagement_id: int) -> dict:
        """List an engagement's findings, sorted by severity then title."""
        return client.get(f"/engagements/{engagement_id}/findings")

    @mcp.tool()
    def finding_create(
        engagement_id: int,
        title: str,
        severity: str,
        details: Optional[str] = None,
        remediation: Optional[str] = None,
        loot_file_ids: Optional[List[int]] = None,
        infra_node_ids: Optional[List[int]] = None,
        credential_ids: Optional[List[int]] = None,
        ioc_ids: Optional[List[int]] = None,
        killchain_entry_ids: Optional[List[int]] = None,
    ) -> dict:
        """Create a finding. severity is one of: critical, high, medium, low,
        informational. details/remediation accept a small set of HTML tags
        (p, strong, em, ul/ol/li, a, headings, code, img); plain text also
        works. The *_ids lists cross-link supporting evidence already
        recorded for this engagement (loot files, infra nodes, credentials,
        IOCs, kill chain entries)."""
        payload = {"title": title, "severity": severity, "details": details, "remediation": remediation}
        payload.update(_correlation_payload(loot_file_ids, infra_node_ids, credential_ids, ioc_ids, killchain_entry_ids))
        return client.post(f"/engagements/{engagement_id}/findings", json=payload)

    @mcp.tool()
    def finding_get(engagement_id: int, finding_id: int) -> dict:
        """Get one finding, including its cross-linked evidence."""
        return client.get(f"/engagements/{engagement_id}/findings/{finding_id}")

    @mcp.tool()
    def finding_update(
        engagement_id: int,
        finding_id: int,
        title: Optional[str] = None,
        severity: Optional[str] = None,
        details: Optional[str] = None,
        remediation: Optional[str] = None,
        loot_file_ids: Optional[List[int]] = None,
        infra_node_ids: Optional[List[int]] = None,
        credential_ids: Optional[List[int]] = None,
        ioc_ids: Optional[List[int]] = None,
        killchain_entry_ids: Optional[List[int]] = None,
    ) -> dict:
        """Update a finding. Only the fields you pass are changed. Passing any
        *_ids list replaces that entire cross-linked collection (not a merge)."""
        payload = {
            k: v for k, v in {"title": title, "severity": severity, "details": details, "remediation": remediation}.items() if v is not None
        }
        payload.update(_correlation_payload(loot_file_ids, infra_node_ids, credential_ids, ioc_ids, killchain_entry_ids))
        return client.patch(f"/engagements/{engagement_id}/findings/{finding_id}", json=payload)

    @mcp.tool()
    def finding_delete(engagement_id: int, finding_id: int) -> dict:
        """Delete a finding."""
        return client.delete(f"/engagements/{engagement_id}/findings/{finding_id}")

    @mcp.tool()
    def finding_report_markdown(engagement_id: int) -> str:
        """Render all of an engagement's findings as a single portable Markdown report."""
        return client.get_text(f"/engagements/{engagement_id}/findings/report.md")
