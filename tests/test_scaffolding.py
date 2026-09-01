from tests.conftest import csrf_token
from tests.test_engagements import _create_engagement


def _save_threat_model(client, engagement_id):
    csrf = csrf_token(client)
    return client.post(
        f"/engagements/{engagement_id}/threat-model/edit",
        data={
            "threat_model": "<p>A ransomware crew.</p>",
            "attack_plan": "<p>Phish then pivot.</p>",
            "objectives": "<p>Reach the finance share.</p>",
            "csrf_token": csrf,
        },
    )


def _create_todo(client, engagement_id, title="Recon the perimeter"):
    csrf = csrf_token(client)
    return client.post(
        f"/engagements/{engagement_id}/todos",
        data={"title": title, "csrf_token": csrf},
    )


def test_scaffolding_select_requires_login(client):
    resp = client.get("/scaffolding")
    assert resp.status_code == 302


def test_scaffolding_select_lists_engagements(admin_client):
    _create_engagement(admin_client, name="Acme Corp Q3")
    resp = admin_client.get("/scaffolding")
    assert resp.status_code == 200
    assert b"Acme Corp Q3" in resp.data


def test_scaffolding_generate_requires_login(client):
    resp = client.get("/scaffolding/1")
    assert resp.status_code == 302


def test_scaffolding_generate_includes_engagement_context(admin_client):
    engagement_id = _create_engagement(admin_client, name="Acme Corp Q3")
    _save_threat_model(admin_client, engagement_id)
    _create_todo(admin_client, engagement_id, "Recon the perimeter")

    resp = admin_client.get(f"/scaffolding/{engagement_id}")
    assert resp.status_code == 200
    body = resp.data.decode()

    assert "Acme Corp Q3" in body
    assert f"engagement_get(engagement_id={engagement_id})" in body
    assert "A ransomware crew." in body
    assert "Reach the finance share." in body
    assert "Recon the perimeter" in body


def test_scaffolding_generate_handles_missing_threat_model(admin_client):
    engagement_id = _create_engagement(admin_client, name="No Plan Yet")
    resp = admin_client.get(f"/scaffolding/{engagement_id}")
    assert resp.status_code == 200
    assert b"No threat model recorded yet" in resp.data


def test_scaffolding_generate_404_for_unknown_engagement(admin_client):
    resp = admin_client.get("/scaffolding/999999")
    assert resp.status_code == 404
