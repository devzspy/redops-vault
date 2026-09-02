def _engagement(api_client):
    resp = api_client.post("/api/v1/engagements", json={"name": "E1", "client_name": "Acme"})
    return resp.get_json()["id"]


def _target_node(api_client, eid, name="dc01.corp.local"):
    resp = api_client.post(
        f"/api/v1/engagements/{eid}/targets/nodes",
        json={"node_type": "hostname", "name": name, "role": "target"},
    )
    assert resp.status_code == 201
    return resp.get_json()["id"]


def test_target_detail_aggregates_correlated_records(api_client):
    eid = _engagement(api_client)
    node_id = _target_node(api_client, eid)
    other_node_id = _target_node(api_client, eid, name="other.corp.local")

    resp = api_client.post(
        f"/api/v1/engagements/{eid}/targets/edges",
        json={"source_node_id": node_id, "target_node_id": other_node_id, "label": "pivot"},
    )
    assert resp.status_code == 201

    resp = api_client.post(
        f"/api/v1/engagements/{eid}/credentials",
        json={"username": "svc_backup", "password": "hunter2hunter2", "source_host": "DC01.CORP.LOCAL"},
    )
    assert resp.status_code == 201
    cred_id = resp.get_json()["id"]

    resp = api_client.post(
        f"/api/v1/engagements/{eid}/iocs",
        json={"host": "dc01.corp.local", "location": r"C:\Temp\evil.exe"},
    )
    assert resp.status_code == 201

    resp = api_client.post(
        f"/api/v1/engagements/{eid}/killchain",
        json={"stage": "installation", "title": "Beacon established", "infra_node_id": node_id},
    )
    assert resp.status_code == 201

    resp = api_client.post(
        f"/api/v1/engagements/{eid}/findings",
        json={"title": "Host finding", "severity": "high", "infra_node_ids": [node_id]},
    )
    assert resp.status_code == 201

    resp = api_client.get(f"/api/v1/engagements/{eid}/targets/nodes/{node_id}/detail")
    assert resp.status_code == 200
    body = resp.get_json()

    assert body["node"]["name"] == "dc01.corp.local"
    assert [e["label"] for e in body["edges"]] == ["pivot"]

    assert len(body["credentials"]) == 1
    assert body["credentials"][0]["id"] == cred_id
    assert "secrets" not in body["credentials"][0]

    assert len(body["iocs"]) == 1
    assert len(body["killchain_entries"]) == 1
    assert len(body["findings"]) == 1
    assert body["loot_files"] == []

    assert len(body["timeline"]) == 4
    assert {event["kind"] for event in body["timeline"]} == {"credential", "ioc", "killchain", "finding"}
    timestamps = [event["timestamp"] for event in body["timeline"]]
    assert timestamps == sorted(timestamps, reverse=True)


def test_target_detail_404s_for_missing_or_non_target_node(api_client):
    eid = _engagement(api_client)

    resp = api_client.get(f"/api/v1/engagements/{eid}/targets/nodes/999/detail")
    assert resp.status_code == 404

    resp = api_client.post(
        f"/api/v1/engagements/{eid}/infrastructure/nodes",
        json={"node_type": "hostname", "name": "redirector.evilcorp.com", "role": "redirector"},
    )
    infra_node_id = resp.get_json()["id"]

    resp = api_client.get(f"/api/v1/engagements/{eid}/targets/nodes/{infra_node_id}/detail")
    assert resp.status_code == 404
