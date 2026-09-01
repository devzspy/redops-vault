from tests.conftest import csrf_token


def _create_engagement(client, name="Findings Co"):
    csrf = csrf_token(client)
    resp = client.post(
        "/engagements",
        data={"name": name, "client_name": name, "description": "", "csrf_token": csrf},
    )
    return int(resp.headers["Location"].rstrip("/").split("/")[-1])


def _create_finding(client, engagement_id, title="SQL Injection in login form", severity="high", details="Found via sqlmap.", remediation="Use parameterized queries."):
    csrf = csrf_token(client)
    resp = client.post(
        f"/engagements/{engagement_id}/findings",
        data={
            "title": title,
            "severity": severity,
            "details": details,
            "remediation": remediation,
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302
    with client.application.app_context():
        from app.models.finding import Finding

        return Finding.query.filter_by(engagement_id=engagement_id, title=title).first().id


def test_create_finding_appears_in_list(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_finding(admin_client, engagement_id)

    resp = admin_client.get(f"/engagements/{engagement_id}/findings")
    assert resp.status_code == 200
    assert b"SQL Injection in login form" in resp.data
    assert b"High" in resp.data


def test_create_finding_rejects_missing_title(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/findings",
        data={"title": "", "severity": "high", "details": "", "remediation": "", "csrf_token": csrf},
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.finding import Finding

        assert Finding.query.filter_by(engagement_id=engagement_id).count() == 0


def test_create_finding_rejects_invalid_severity(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/findings",
        data={"title": "Bad severity", "severity": "apocalyptic", "details": "", "remediation": "", "csrf_token": csrf},
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.finding import Finding

        assert Finding.query.filter_by(engagement_id=engagement_id).count() == 0


def test_edit_and_delete_finding(admin_client):
    engagement_id = _create_engagement(admin_client)
    finding_id = _create_finding(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/findings/{finding_id}/edit",
        data={
            "title": "Renamed finding",
            "severity": "critical",
            "details": "Updated details.",
            "remediation": "Updated remediation.",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    resp = admin_client.get(f"/engagements/{engagement_id}/findings")
    assert b"Renamed finding" in resp.data
    assert b"Critical" in resp.data

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/findings/{finding_id}/delete",
        data={"csrf_token": csrf},
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.finding import Finding

        assert Finding.query.get(finding_id) is None


def test_markdown_export_contains_required_fields(admin_client):
    engagement_id = _create_engagement(admin_client, name="Acme Corp")
    _create_finding(
        admin_client,
        engagement_id,
        title="Weak Password Policy",
        severity="medium",
        details="Passwords as short as 4 characters were accepted.",
        remediation="Enforce a minimum length of 14 characters.",
    )

    resp = admin_client.get(f"/engagements/{engagement_id}/findings/report.md")
    assert resp.status_code == 200
    assert resp.mimetype == "text/markdown"
    assert "attachment" in resp.headers["Content-Disposition"]

    md = resp.data.decode()
    assert "# Findings Report — Acme Corp" in md
    assert "## [MEDIUM] Weak Password Policy" in md
    assert "**Severity:** Medium" in md
    assert "### Details" in md
    assert "Passwords as short as 4 characters were accepted." in md
    assert "### Remediation" in md
    assert "Enforce a minimum length of 14 characters." in md


def test_markdown_export_sorts_critical_first(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_finding(admin_client, engagement_id, title="Low issue", severity="low")
    _create_finding(admin_client, engagement_id, title="Critical issue", severity="critical")
    _create_finding(admin_client, engagement_id, title="Medium issue", severity="medium")

    resp = admin_client.get(f"/engagements/{engagement_id}/findings/report.md")
    md = resp.data.decode()

    assert md.index("Critical issue") < md.index("Medium issue") < md.index("Low issue")


def test_markdown_export_with_no_findings(admin_client):
    engagement_id = _create_engagement(admin_client)

    resp = admin_client.get(f"/engagements/{engagement_id}/findings/report.md")
    assert resp.status_code == 200
    assert "No findings recorded yet" in resp.data.decode()


def test_deleting_engagement_deletes_its_findings(admin_client):
    engagement_id = _create_engagement(admin_client)
    finding_id = _create_finding(admin_client, engagement_id)

    with admin_client.application.app_context():
        from app.extensions import db
        from app.models.engagement import Engagement
        from app.models.finding import Finding

        engagement = Engagement.query.get(engagement_id)
        db.session.delete(engagement)
        db.session.commit()

        assert Finding.query.get(finding_id) is None


def test_finding_details_html_is_sanitized_on_create(admin_client):
    engagement_id = _create_engagement(admin_client)
    finding_id = _create_finding(
        admin_client,
        engagement_id,
        title="XSS test",
        details='<p>Safe text</p><script>alert(1)</script><img src="x" onerror="alert(1)">',
        remediation="<p>Fine</p>",
    )

    with admin_client.application.app_context():
        from app.models.finding import Finding

        finding = Finding.query.get(finding_id)
        assert "<script>" not in finding.details
        assert "onerror" not in finding.details
        assert "<p>Safe text</p>" in finding.details

    resp = admin_client.get(f"/engagements/{engagement_id}/findings")
    assert b"<script>" not in resp.data
    assert b"Safe text" in resp.data


def test_blank_wysiwyg_content_stored_as_null(admin_client):
    engagement_id = _create_engagement(admin_client)
    finding_id = _create_finding(admin_client, engagement_id, details="<p><br></p>", remediation="<p><br></p>")

    with admin_client.application.app_context():
        from app.models.finding import Finding

        finding = Finding.query.get(finding_id)
        assert finding.details is None
        assert finding.remediation is None


def test_findings_list_has_collapse_and_back_to_top(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_finding(admin_client, engagement_id)

    resp = admin_client.get(f"/engagements/{engagement_id}/findings")
    html = resp.data.decode()
    assert 'data-bs-toggle="collapse"' in html
    assert 'id="back-to-top"' in html


def test_finding_can_attach_loot_file(admin_client):
    import io

    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/loot/upload",
        data={
            "file": (io.BytesIO(b"evidence"), "screenshot.png"),
            "category": "screenshot",
            "csrf_token": csrf,
        },
        content_type="multipart/form-data",
    )
    file_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/findings",
        data={
            "title": "Finding with evidence",
            "severity": "high",
            "details": "<p>See attached.</p>",
            "remediation": "",
            "loot_file_ids": [str(file_id)],
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.finding import Finding

        finding = Finding.query.filter_by(engagement_id=engagement_id, title="Finding with evidence").first()
        assert len(finding.loot_files) == 1
        assert finding.loot_files[0].original_filename == "screenshot.png"

    resp = admin_client.get(f"/engagements/{engagement_id}/findings")
    assert b"screenshot.png" in resp.data


def test_markdown_export_converts_rich_text_to_markdown_syntax(admin_client):
    engagement_id = _create_engagement(admin_client, name="Rich Co")
    _create_finding(
        admin_client,
        engagement_id,
        title="Formatted finding",
        details="<p>The form is <strong>vulnerable</strong>.</p><ul><li>Step one</li><li>Step two</li></ul>",
        remediation='<p>See <a href="https://owasp.org">OWASP</a>.</p>',
    )

    resp = admin_client.get(f"/engagements/{engagement_id}/findings/report.md")
    md = resp.data.decode()

    assert "**vulnerable**" in md
    assert "- Step one" in md
    assert "- Step two" in md
    assert "[OWASP](https://owasp.org)" in md
    assert "<p>" not in md
    assert "<strong>" not in md
