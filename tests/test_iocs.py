from tests.conftest import csrf_token


def _create_engagement(client):
    csrf = csrf_token(client)
    resp = client.post(
        "/engagements",
        data={"name": "IOC Co", "client_name": "IOC Co", "description": "", "csrf_token": csrf},
    )
    return int(resp.headers["Location"].rstrip("/").split("/")[-1])


def _create_node(client, engagement_id, name="dc01.corp.local", role="target"):
    endpoint = "targets" if role in ("target", "victim") else "infrastructure/nodes"
    csrf = csrf_token(client)
    resp = client.post(
        f"/engagements/{engagement_id}/{endpoint}",
        data={
            "node_type": "hostname",
            "name": name,
            "role": role,
            "provider": "",
            "region": "",
            "notes": "",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302
    return name


def _create_ioc(client, engagement_id, **overrides):
    csrf = csrf_token(client)
    data = {
        "host": "dc01.corp.local",
        "location": r"C:\Windows\Temp\evil.exe",
        "hash_type": "sha256",
        "hash_value": "a" * 64,
        "dropped_at": "2026-08-01T10:30",
        "notes": "",
        "csrf_token": csrf,
    }
    data.update(overrides)
    resp = client.post(f"/engagements/{engagement_id}/iocs", data=data)
    return resp


def test_create_ioc_appears_in_list(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_node(admin_client, engagement_id)
    resp = _create_ioc(admin_client, engagement_id)
    assert resp.status_code == 302

    list_resp = admin_client.get(f"/engagements/{engagement_id}/iocs")
    assert list_resp.status_code == 200
    assert b"dc01.corp.local" in list_resp.data
    assert rb"C:\Windows\Temp\evil.exe" in list_resp.data
    assert b"SHA256" in list_resp.data
    assert b"a" * 64 in list_resp.data


def test_ioc_persists_all_fields(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_node(admin_client, engagement_id)
    _create_ioc(admin_client, engagement_id)

    with admin_client.application.app_context():
        from app.models.ioc import IOC

        ioc = IOC.query.filter_by(engagement_id=engagement_id).first()
        assert ioc.host == "dc01.corp.local"
        assert ioc.location == r"C:\Windows\Temp\evil.exe"
        assert ioc.hash_type == "sha256"
        assert ioc.hash_value == "a" * 64
        assert ioc.dropped_at.strftime("%Y-%m-%dT%H:%M") == "2026-08-01T10:30"
        assert ioc.added_by.username == "admin"


def test_host_dropdown_only_shows_target_role_nodes(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_node(admin_client, engagement_id, name="target01.corp.local", role="target")
    _create_node(admin_client, engagement_id, name="c2.evilcorp.test", role="C2")

    form_page = admin_client.get(f"/engagements/{engagement_id}/iocs/new")
    assert form_page.status_code == 200
    assert b"target01.corp.local" in form_page.data
    assert b"c2.evilcorp.test" not in form_page.data


def test_invalid_hash_type_rejected(admin_client):
    engagement_id = _create_engagement(admin_client)
    resp = _create_ioc(admin_client, engagement_id, hash_type="sha1", host="", location="")
    assert resp.status_code == 400

    with admin_client.application.app_context():
        from app.models.ioc import IOC

        assert IOC.query.filter_by(engagement_id=engagement_id).count() == 0


def test_ioc_fields_are_optional(admin_client):
    engagement_id = _create_engagement(admin_client)
    resp = _create_ioc(
        admin_client, engagement_id, host="", location="", hash_type="", hash_value="", dropped_at=""
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.ioc import IOC

        ioc = IOC.query.filter_by(engagement_id=engagement_id).first()
        assert ioc.host is None
        assert ioc.location is None
        assert ioc.hash_type is None
        assert ioc.hash_value is None
        assert ioc.dropped_at is None


def test_edit_ioc_updates_fields(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_node(admin_client, engagement_id)
    _create_ioc(admin_client, engagement_id)

    with admin_client.application.app_context():
        from app.models.ioc import IOC

        ioc_id = IOC.query.filter_by(engagement_id=engagement_id).first().id

    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/iocs/{ioc_id}/edit",
        data={
            "host": "",
            "location": "/tmp/evil.sh",
            "hash_type": "md5",
            "hash_value": "b" * 32,
            "dropped_at": "",
            "notes": "updated",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.ioc import IOC

        ioc = IOC.query.get(ioc_id)
        assert ioc.host is None
        assert ioc.location == "/tmp/evil.sh"
        assert ioc.hash_type == "md5"
        assert ioc.hash_value == "b" * 32
        assert ioc.notes == "updated"


def test_delete_ioc(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_ioc(admin_client, engagement_id, host="", location="loot.bin")

    with admin_client.application.app_context():
        from app.models.ioc import IOC

        ioc_id = IOC.query.filter_by(engagement_id=engagement_id).first().id

    csrf = csrf_token(admin_client)
    resp = admin_client.post(f"/engagements/{engagement_id}/iocs/{ioc_id}/delete", data={"csrf_token": csrf})
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.ioc import IOC

        assert IOC.query.get(ioc_id) is None


def test_ioc_appears_in_killchain_report(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_node(admin_client, engagement_id)
    _create_ioc(admin_client, engagement_id)

    resp = admin_client.get(f"/engagements/{engagement_id}/killchain/report")
    assert resp.status_code == 200
    assert b"Indicators of Compromise" in resp.data
    assert b"dc01.corp.local" in resp.data
    assert rb"C:\Windows\Temp\evil.exe" in resp.data
    assert b"a" * 64 in resp.data


def test_ioc_appears_in_killchain_pdf_report(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_node(admin_client, engagement_id)
    _create_ioc(admin_client, engagement_id)

    resp = admin_client.get(f"/engagements/{engagement_id}/killchain/report.pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data[:5] == b"%PDF-"


def test_deleting_engagement_deletes_its_iocs(admin_client):
    engagement_id = _create_engagement(admin_client)
    _create_ioc(admin_client, engagement_id, host="", location="loot.bin")

    with admin_client.application.app_context():
        from app.extensions import db
        from app.models.engagement import Engagement
        from app.models.ioc import IOC

        assert IOC.query.filter_by(engagement_id=engagement_id).count() == 1
        engagement = Engagement.query.get(engagement_id)
        db.session.delete(engagement)
        db.session.commit()
        assert IOC.query.filter_by(engagement_id=engagement_id).count() == 0
