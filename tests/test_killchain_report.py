from tests.conftest import csrf_token


def _create_engagement(client):
    csrf = csrf_token(client)
    resp = client.post(
        "/engagements",
        data={"name": "Kill Chain Co", "client_name": "Kill Chain Co", "description": "", "csrf_token": csrf},
    )
    return int(resp.headers["Location"].rstrip("/").split("/")[-1])


def _create_entry(client, engagement_id, stage="delivery", title="Sent phishing email"):
    csrf = csrf_token(client)
    resp = client.post(
        f"/engagements/{engagement_id}/killchain",
        data={
            "stage": stage,
            "title": title,
            "description": "Delivered a malicious macro document via email.",
            "host": "mail01.corp.local",
            "occurred_at": "2026-01-15T09:30",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302
    return resp


def test_create_killchain_entry_appears_on_timeline(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_entry(admin_client, engagement_id)

    resp = admin_client.get(f"/engagements/{engagement_id}/killchain")
    assert resp.status_code == 200
    assert b"Sent phishing email" in resp.data


def test_killchain_entry_rejects_invalid_stage(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/killchain",
        data={"stage": "not-a-real-stage", "title": "Bad entry", "csrf_token": csrf},
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.killchain import KillChainEntry

        assert KillChainEntry.query.filter_by(engagement_id=engagement_id).count() == 0


def test_html_report_contains_entry_details(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_entry(admin_client, engagement_id)

    resp = admin_client.get(f"/engagements/{engagement_id}/killchain/report")
    assert resp.status_code == 200
    assert b"Sent phishing email" in resp.data
    assert b"Kill Chain Co" in resp.data


def test_pdf_report_downloads_as_pdf(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_entry(admin_client, engagement_id)

    resp = admin_client.get(f"/engagements/{engagement_id}/killchain/report.pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data[:5] == b"%PDF-"
    assert "attachment" in resp.headers["Content-Disposition"]


def test_technique_mapping_links_loot_to_killchain_entry(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_entry(admin_client, engagement_id)

    with admin_client.application.app_context():
        from app.extensions import db
        from app.models.attack import AttackTactic, AttackTechnique
        from app.models.killchain import KillChainEntry

        tactic = AttackTactic(attack_id="TA0001", name="Initial Access", short_name="initial-access")
        db.session.add(tactic)
        db.session.flush()
        technique = AttackTechnique(attack_id="T1566", name="Phishing", tactics=[tactic])
        db.session.add(technique)
        db.session.commit()
        entry_id = KillChainEntry.query.filter_by(engagement_id=engagement_id).first().id

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/killchain/{entry_id}/map-technique",
        data={"attack_id": "T1566", "csrf_token": csrf},
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.killchain import TechniqueMapping

        mapping = TechniqueMapping.query.filter_by(killchain_entry_id=entry_id).first()
        assert mapping is not None
        assert mapping.technique.attack_id == "T1566"

    report = admin_client.get(f"/engagements/{engagement_id}/killchain/report")
    assert b"T1566" in report.data or b"Phishing" in report.data


def test_entry_with_start_and_end_time_persists_both(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/killchain",
        data={
            "stage": "reconnaissance",
            "title": "nmap scan",
            "occurred_at": "2026-01-15T09:00",
            "occurred_ended_at": "2026-01-15T09:45",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.killchain import KillChainEntry

        entry = KillChainEntry.query.filter_by(engagement_id=engagement_id).first()
        assert entry.occurred_at.strftime("%Y-%m-%dT%H:%M") == "2026-01-15T09:00"
        assert entry.occurred_ended_at.strftime("%Y-%m-%dT%H:%M") == "2026-01-15T09:45"
        assert entry.occurred_range_label() == "2026-01-15 09:00 – 09:45"


def test_entry_end_time_on_different_day_shows_full_dates(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/killchain",
        data={
            "stage": "reconnaissance",
            "title": "multi-day scan",
            "occurred_at": "2026-01-15T23:50",
            "occurred_ended_at": "2026-01-16T00:10",
            "csrf_token": csrf,
        },
    )

    with admin_client.application.app_context():
        from app.models.killchain import KillChainEntry

        entry = KillChainEntry.query.filter_by(engagement_id=engagement_id).first()
        assert entry.occurred_range_label() == "2026-01-15 23:50 – 2026-01-16 00:10"


def test_create_entry_rejects_end_before_start(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/killchain",
        data={
            "stage": "reconnaissance",
            "title": "bad range",
            "occurred_at": "2026-01-15T10:00",
            "occurred_ended_at": "2026-01-15T09:00",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.killchain import KillChainEntry

        assert KillChainEntry.query.filter_by(engagement_id=engagement_id).count() == 0


def test_edit_entry_rejects_end_before_start(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_entry(admin_client, engagement_id)

    with admin_client.application.app_context():
        from app.models.killchain import KillChainEntry

        entry_id = KillChainEntry.query.filter_by(engagement_id=engagement_id).first().id

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/killchain/{entry_id}/edit",
        data={
            "stage": "reconnaissance",
            "title": "bad range",
            "occurred_at": "2026-01-15T10:00",
            "occurred_ended_at": "2026-01-15T09:00",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 400


def test_timeline_shows_occurred_range(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/killchain",
        data={
            "stage": "reconnaissance",
            "title": "nmap scan",
            "occurred_at": "2026-01-15T09:00",
            "occurred_ended_at": "2026-01-15T09:45",
            "csrf_token": csrf,
        },
    )

    resp = admin_client.get(f"/engagements/{engagement_id}/killchain")
    assert resp.status_code == 200
    assert b"2026-01-15 09:00" in resp.data
    assert b"09:45" in resp.data


def test_report_shows_occurred_range(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/killchain",
        data={
            "stage": "reconnaissance",
            "title": "nmap scan",
            "occurred_at": "2026-01-15T09:00",
            "occurred_ended_at": "2026-01-15T09:45",
            "csrf_token": csrf,
        },
    )

    resp = admin_client.get(f"/engagements/{engagement_id}/killchain/report")
    assert resp.status_code == 200
    assert b"09:00" in resp.data and b"09:45" in resp.data


def test_killchain_activity_log_entry_captures_occurred_range(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/killchain",
        data={
            "stage": "reconnaissance",
            "title": "nmap scan",
            "occurred_at": "2026-01-15T09:00",
            "occurred_ended_at": "2026-01-15T09:45",
            "csrf_token": csrf,
        },
    )

    with admin_client.application.app_context():
        from app.models.activity import ActivityLogEntry

        entry = ActivityLogEntry.query.filter_by(
            engagement_id=engagement_id, entity_type="killchain_entry", action="created"
        ).first()
        assert entry is not None
        assert entry.occurred_started_at.strftime("%Y-%m-%dT%H:%M") == "2026-01-15T09:00"
        assert entry.occurred_ended_at.strftime("%Y-%m-%dT%H:%M") == "2026-01-15T09:45"
        assert entry.created_at is not None
        # created_at (recorded) should not be backdated to the occurred time
        assert entry.created_at.year >= 2026
