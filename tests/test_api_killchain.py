def _engagement(api_client):
    resp = api_client.post("/api/v1/engagements", json={"name": "E1", "client_name": "Acme"})
    return resp.get_json()["id"]


def test_create_list_get_update_delete_entry(api_client):
    eid = _engagement(api_client)
    resp = api_client.post(
        f"/api/v1/engagements/{eid}/killchain",
        json={"stage": "delivery", "title": "Phishing email sent", "occurred_at": "2026-01-01T10:00:00"},
    )
    assert resp.status_code == 201
    entry = resp.get_json()
    assert entry["stage_label"] == "Delivery"

    resp = api_client.get(f"/api/v1/engagements/{eid}/killchain")
    assert len(resp.get_json()["entries"]) == 1

    resp = api_client.get(f"/api/v1/engagements/{eid}/killchain/{entry['id']}")
    assert resp.status_code == 200

    resp = api_client.patch(f"/api/v1/engagements/{eid}/killchain/{entry['id']}", json={"stage": "exploitation"})
    assert resp.get_json()["stage"] == "exploitation"

    resp = api_client.delete(f"/api/v1/engagements/{eid}/killchain/{entry['id']}")
    assert resp.status_code == 204


def test_invalid_stage_rejected(api_client):
    eid = _engagement(api_client)
    resp = api_client.post(f"/api/v1/engagements/{eid}/killchain", json={"stage": "nope", "title": "x"})
    assert resp.status_code == 400


def test_end_before_start_rejected(api_client):
    eid = _engagement(api_client)
    resp = api_client.post(
        f"/api/v1/engagements/{eid}/killchain",
        json={
            "stage": "reconnaissance",
            "title": "scan",
            "occurred_at": "2026-01-02T10:00:00",
            "occurred_ended_at": "2026-01-01T10:00:00",
        },
    )
    assert resp.status_code == 400


def test_report_endpoints(api_client):
    eid = _engagement(api_client)
    api_client.post(f"/api/v1/engagements/{eid}/killchain", json={"stage": "delivery", "title": "x"})

    resp = api_client.get(f"/api/v1/engagements/{eid}/killchain/report")
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"

    resp = api_client.get(f"/api/v1/engagements/{eid}/killchain/report.pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"


def test_technique_mapping_lifecycle(app, api_client):
    eid = _engagement(api_client)
    with app.app_context():
        from app.extensions import db
        from app.models.attack import AttackTactic, AttackTechnique

        tactic = AttackTactic(attack_id="TA0001", name="Initial Access", short_name="initial-access")
        technique = AttackTechnique(attack_id="T1566", name="Phishing")
        technique.tactics.append(tactic)
        db.session.add_all([tactic, technique])
        db.session.commit()

    entry = api_client.post(
        f"/api/v1/engagements/{eid}/killchain", json={"stage": "delivery", "title": "Phish"}
    ).get_json()

    resp = api_client.post(
        f"/api/v1/engagements/{eid}/killchain/{entry['id']}/map-technique", json={"attack_id": "T1566"}
    )
    assert resp.status_code == 201
    mapping = resp.get_json()
    assert mapping["technique"]["attack_id"] == "T1566"

    resp = api_client.get("/api/v1/attack/techniques/T1566")
    assert resp.status_code == 200
    assert len(resp.get_json()["mappings"]) == 1

    resp = api_client.delete(f"/api/v1/technique-mappings/{mapping['id']}")
    assert resp.status_code == 204
