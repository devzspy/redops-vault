import io
from datetime import datetime

from tests.conftest import csrf_token


def _create_engagement(client, name="Activity Co"):
    csrf = csrf_token(client)
    resp = client.post(
        "/engagements",
        data={"name": name, "client_name": name, "description": "", "csrf_token": csrf},
    )
    return int(resp.headers["Location"].rstrip("/").split("/")[-1])


def _entries(client, engagement_id):
    with client.application.app_context():
        from app.models.activity import ActivityLogEntry

        return (
            ActivityLogEntry.query.filter_by(engagement_id=engagement_id)
            .order_by(ActivityLogEntry.id.asc())
            .all()
        )


def test_creating_engagement_logs_activity_with_timestamp(admin_client):
    engagement_id = _create_engagement(admin_client)

    entries = _entries(admin_client, engagement_id)
    assert len(entries) == 1
    assert entries[0].entity_type == "engagement"
    assert entries[0].action == "created"
    assert entries[0].actor_label == "admin"
    assert entries[0].created_at is not None
    assert "Activity Co" in entries[0].summary


def test_status_change_and_archive_are_logged(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)

    admin_client.post(
        f"/engagements/{engagement_id}/status", data={"status": "active", "csrf_token": csrf}
    )
    admin_client.post(f"/engagements/{engagement_id}/archive", data={"csrf_token": csrf})

    entries = _entries(admin_client, engagement_id)
    actions = [e.action for e in entries]
    assert "status_changed" in actions
    assert "archived" in actions


def test_loot_upload_edit_delete_are_logged(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)

    resp = admin_client.post(
        f"/engagements/{engagement_id}/loot/upload",
        data={
            "file": (io.BytesIO(b"loot bytes"), "evil.exe"),
            "category": "other",
            "csrf_token": csrf,
        },
        content_type="multipart/form-data",
    )
    file_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/loot/{file_id}/edit",
        data={"category": "document", "csrf_token": csrf},
    )

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/loot/{file_id}/delete", data={"csrf_token": csrf}
    )

    entries = [e for e in _entries(admin_client, engagement_id) if e.entity_type == "loot_file"]
    assert [e.action for e in entries] == ["created", "updated", "deleted"]
    assert all("evil.exe" in e.summary for e in entries)


def test_credential_create_edit_delete_are_logged(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)

    admin_client.post(
        f"/engagements/{engagement_id}/credentials",
        data={
            "username": "svc_backup",
            "password": "hunter2hunter2",
            "hash": "",
            "domain": "",
            "source_host": "",
            "csrf_token": csrf,
        },
    )

    with admin_client.application.app_context():
        from app.models.loot import Credential

        cred_id = Credential.query.filter_by(engagement_id=engagement_id).first().id

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/credentials/{cred_id}/edit",
        data={
            "username": "svc_backup2",
            "password": "",
            "hash": "",
            "domain": "",
            "source_host": "",
            "csrf_token": csrf,
        },
    )

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/credentials/{cred_id}/delete", data={"csrf_token": csrf}
    )

    entries = [e for e in _entries(admin_client, engagement_id) if e.entity_type == "credential"]
    assert [e.action for e in entries] == ["created", "updated", "deleted"]


def test_killchain_entry_lifecycle_is_logged(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)

    admin_client.post(
        f"/engagements/{engagement_id}/killchain",
        data={"stage": "delivery", "title": "Phishing email", "csrf_token": csrf},
    )

    with admin_client.application.app_context():
        from app.models.killchain import KillChainEntry

        entry_id = KillChainEntry.query.filter_by(engagement_id=engagement_id).first().id

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/killchain/{entry_id}/edit",
        data={"stage": "exploitation", "title": "Phishing email", "csrf_token": csrf},
    )

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/killchain/{entry_id}/delete", data={"csrf_token": csrf}
    )

    entries = [e for e in _entries(admin_client, engagement_id) if e.entity_type == "killchain_entry"]
    assert [e.action for e in entries] == ["created", "updated", "deleted"]


def test_finding_lifecycle_is_logged(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)

    admin_client.post(
        f"/engagements/{engagement_id}/findings",
        data={"title": "Weak passwords", "severity": "medium", "csrf_token": csrf},
    )

    entries = [e for e in _entries(admin_client, engagement_id) if e.entity_type == "finding"]
    assert len(entries) == 1
    assert entries[0].action == "created"
    assert "Weak passwords" in entries[0].summary


def test_ioc_lifecycle_is_logged(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)

    admin_client.post(
        f"/engagements/{engagement_id}/iocs",
        data={"location": r"C:\Temp\evil.exe", "csrf_token": csrf},
    )

    entries = [e for e in _entries(admin_client, engagement_id) if e.entity_type == "ioc"]
    assert len(entries) == 1
    assert entries[0].action == "created"
    assert "evil.exe" in entries[0].summary


def test_infrastructure_node_lifecycle_is_logged(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)

    admin_client.post(
        f"/engagements/{engagement_id}/targets",
        data={
            "node_type": "hostname",
            "name": "victim01.corp.local",
            "role": "target",
            "status": "healthy",
            "csrf_token": csrf,
        },
    )

    entries = [e for e in _entries(admin_client, engagement_id) if e.entity_type == "infrastructure_node"]
    assert len(entries) == 1
    assert "victim01.corp.local" in entries[0].summary


def test_infrastructure_edge_lifecycle_is_logged(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)

    def _make_node(name):
        nonlocal csrf
        admin_client.post(
            f"/engagements/{engagement_id}/infrastructure/nodes",
            data={"node_type": "hostname", "name": name, "role": "", "csrf_token": csrf},
        )
        csrf = csrf_token(admin_client)

    _make_node("a.corp.local")
    _make_node("b.corp.local")

    with admin_client.application.app_context():
        from app.models.infrastructure import InfrastructureNode

        nodes = InfrastructureNode.query.filter_by(engagement_id=engagement_id).order_by(
            InfrastructureNode.name.asc()
        ).all()
        source_id, target_id = nodes[0].id, nodes[1].id

    admin_client.post(
        f"/engagements/{engagement_id}/infrastructure/edges",
        data={
            "source_node_id": source_id,
            "target_node_id": target_id,
            "label": "HTTPS",
            "csrf_token": csrf,
        },
    )

    entries = [e for e in _entries(admin_client, engagement_id) if e.entity_type == "infrastructure_edge"]
    assert len(entries) == 1
    assert entries[0].action == "created"
    assert "a.corp.local" in entries[0].summary
    assert "b.corp.local" in entries[0].summary


def test_technique_mapping_logged(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)

    admin_client.post(
        f"/engagements/{engagement_id}/loot/upload",
        data={"file": (io.BytesIO(b"x"), "loot.txt"), "category": "other", "csrf_token": csrf},
        content_type="multipart/form-data",
    )

    with admin_client.application.app_context():
        from app.extensions import db
        from app.models.attack import AttackTechnique
        from app.models.loot import LootFile

        technique = AttackTechnique(attack_id="T1566", name="Phishing")
        db.session.add(technique)
        db.session.commit()
        file_id = LootFile.query.filter_by(engagement_id=engagement_id).first().id

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/loot/{file_id}/map-technique",
        data={"attack_id": "T1566", "csrf_token": csrf},
    )

    entries = [e for e in _entries(admin_client, engagement_id) if e.entity_type == "technique_mapping"]
    assert len(entries) == 1
    assert entries[0].action == "mapped"
    assert "T1566" in entries[0].summary


def test_activity_appears_on_overview_page_most_recent_first(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/engagements/{engagement_id}/status", data={"status": "active", "csrf_token": csrf}
    )

    resp = admin_client.get(f"/engagements/{engagement_id}")
    assert resp.status_code == 200
    assert b"Activity" in resp.data
    assert b"Changed status to Active" in resp.data
    assert b"Created engagement" in resp.data

    changed_index = resp.data.index(b"Changed status to Active")
    created_index = resp.data.index(b"Created engagement")
    assert changed_index < created_index


def test_deleting_engagement_deletes_its_activity_log(admin_client):
    engagement_id = _create_engagement(admin_client)

    with admin_client.application.app_context():
        from app.extensions import db
        from app.models.activity import ActivityLogEntry
        from app.models.engagement import Engagement

        assert ActivityLogEntry.query.filter_by(engagement_id=engagement_id).count() > 0
        engagement = Engagement.query.get(engagement_id)
        db.session.delete(engagement)
        db.session.commit()
        assert ActivityLogEntry.query.filter_by(engagement_id=engagement_id).count() == 0


def test_activity_log_is_scoped_per_engagement(admin_client):
    engagement_a = _create_engagement(admin_client, name="Engagement A")
    engagement_b = _create_engagement(admin_client, name="Engagement B")

    entries_a = _entries(admin_client, engagement_a)
    entries_b = _entries(admin_client, engagement_b)

    assert len(entries_a) == 1
    assert len(entries_b) == 1
    assert "Engagement A" in entries_a[0].summary
    assert "Engagement B" in entries_b[0].summary


def test_occurred_range_label_no_start_returns_none(app):
    with app.app_context():
        from app.models.activity import ActivityLogEntry

        entry = ActivityLogEntry(
            engagement_id=1, actor_label="admin", entity_type="note", action="created", summary="x"
        )
        assert entry.occurred_range_label() is None


def test_occurred_range_label_start_only(app):
    with app.app_context():
        from app.models.activity import ActivityLogEntry

        entry = ActivityLogEntry(
            engagement_id=1,
            actor_label="admin",
            entity_type="note",
            action="created",
            summary="x",
            occurred_started_at=datetime(2026, 1, 15, 9, 0),
        )
        assert entry.occurred_range_label() == "2026-01-15 09:00"


def test_occurred_range_label_same_day_range(app):
    with app.app_context():
        from app.models.activity import ActivityLogEntry

        entry = ActivityLogEntry(
            engagement_id=1,
            actor_label="admin",
            entity_type="note",
            action="created",
            summary="x",
            occurred_started_at=datetime(2026, 1, 15, 9, 0),
            occurred_ended_at=datetime(2026, 1, 15, 9, 45),
        )
        assert entry.occurred_range_label() == "2026-01-15 09:00 – 09:45"


def test_occurred_range_label_cross_day_range(app):
    with app.app_context():
        from app.models.activity import ActivityLogEntry

        entry = ActivityLogEntry(
            engagement_id=1,
            actor_label="admin",
            entity_type="note",
            action="created",
            summary="x",
            occurred_started_at=datetime(2026, 1, 15, 23, 50),
            occurred_ended_at=datetime(2026, 1, 16, 0, 10),
        )
        assert entry.occurred_range_label() == "2026-01-15 23:50 – 2026-01-16 00:10"


def test_overview_page_shows_occurred_and_recorded_columns(admin_client):
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

    resp = admin_client.get(f"/engagements/{engagement_id}")
    assert resp.status_code == 200
    assert b"Occurred" in resp.data
    assert b"Recorded" in resp.data
    assert b"2026-01-15 09:00" in resp.data
    assert b"09:45" in resp.data
