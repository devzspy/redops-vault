def _engagement(api_client):
    resp = api_client.post("/api/v1/engagements", json={"name": "E1", "client_name": "Acme"})
    return resp.get_json()["id"]


def test_infrastructure_node_and_edge_crud(api_client):
    eid = _engagement(api_client)
    n1 = api_client.post(
        f"/api/v1/engagements/{eid}/infrastructure/nodes",
        json={"node_type": "hostname", "name": "redirector1", "role": "redirector"},
    ).get_json()
    n2 = api_client.post(
        f"/api/v1/engagements/{eid}/infrastructure/nodes",
        json={"node_type": "hostname", "name": "teamserver1", "role": "team_server"},
    ).get_json()

    resp = api_client.get(f"/api/v1/engagements/{eid}/infrastructure/nodes")
    assert len(resp.get_json()["nodes"]) == 2

    resp = api_client.post(
        f"/api/v1/engagements/{eid}/infrastructure/nodes/{n1['id']}/services", json={"name": "https", "port": 443}
    )
    assert resp.status_code == 201

    resp = api_client.post(
        f"/api/v1/engagements/{eid}/infrastructure/edges",
        json={"source_node_id": n1["id"], "target_node_id": n2["id"], "label": "forwards to"},
    )
    assert resp.status_code == 201
    edge = resp.get_json()

    resp = api_client.get(f"/api/v1/engagements/{eid}/infrastructure/graph.json")
    assert resp.status_code == 200
    assert len(resp.get_json()["nodes"]) == 2

    assert api_client.delete(f"/api/v1/engagements/{eid}/infrastructure/edges/{edge['id']}").status_code == 204
    assert api_client.delete(f"/api/v1/engagements/{eid}/infrastructure/nodes/{n1['id']}").status_code == 204


def test_infrastructure_rejects_target_role(api_client):
    eid = _engagement(api_client)
    resp = api_client.post(
        f"/api/v1/engagements/{eid}/infrastructure/nodes",
        json={"node_type": "hostname", "name": "victim1", "role": "target"},
    )
    assert resp.status_code == 400


def test_targets_crud_and_edge_requires_target_roles(api_client):
    eid = _engagement(api_client)
    t1 = api_client.post(
        f"/api/v1/engagements/{eid}/targets/nodes",
        json={"node_type": "hostname", "name": "victim1", "role": "target"},
    ).get_json()
    t2 = api_client.post(
        f"/api/v1/engagements/{eid}/targets/nodes",
        json={"node_type": "database", "name": "sqlserver1", "role": "victim"},
    ).get_json()

    resp = api_client.post(
        f"/api/v1/engagements/{eid}/targets/edges", json={"source_node_id": t1["id"], "target_node_id": t2["id"]}
    )
    assert resp.status_code == 201

    resp = api_client.post(
        f"/api/v1/engagements/{eid}/targets/nodes", json={"node_type": "hostname", "name": "bad", "role": "redirector"}
    )
    assert resp.status_code == 400


def test_ioc_crud(api_client):
    eid = _engagement(api_client)
    resp = api_client.post(
        f"/api/v1/engagements/{eid}/iocs", json={"host": "evil.com", "hash_type": "sha256", "hash_value": "abc123"}
    )
    assert resp.status_code == 201
    ioc = resp.get_json()

    resp = api_client.patch(f"/api/v1/engagements/{eid}/iocs/{ioc['id']}", json={"notes": "malware dropper"})
    assert resp.get_json()["notes"] == "malware dropper"

    assert api_client.delete(f"/api/v1/engagements/{eid}/iocs/{ioc['id']}").status_code == 204


def test_ioc_rejects_invalid_hash_type(api_client):
    eid = _engagement(api_client)
    resp = api_client.post(f"/api/v1/engagements/{eid}/iocs", json={"hash_type": "sha1"})
    assert resp.status_code == 400


def test_threat_model_get_and_upsert(api_client):
    eid = _engagement(api_client)
    resp = api_client.get(f"/api/v1/engagements/{eid}/threat-model")
    assert resp.get_json()["threat_model"] is None

    resp = api_client.put(
        f"/api/v1/engagements/{eid}/threat-model",
        json={"threat_model": "<p>APT29 emulation</p>", "attack_plan": "<p>plan</p>", "objectives": "<p>obj</p>"},
    )
    assert resp.status_code == 200
    plan = resp.get_json()["threat_model"]
    assert "APT29 emulation" in plan["threat_model"]
    assert plan["is_empty"] is False

    resp = api_client.get(f"/api/v1/engagements/{eid}/threat-model")
    assert "APT29" in resp.get_json()["threat_model"]["threat_model"]


def test_activity_log_lists_entries(api_client):
    eid = _engagement(api_client)
    api_client.post(f"/api/v1/engagements/{eid}/iocs", json={"host": "evil.com"})

    resp = api_client.get(f"/api/v1/engagements/{eid}/activity")
    assert resp.status_code == 200
    entries = resp.get_json()["activity"]
    assert any(e["entity_type"] == "ioc" for e in entries)


def test_attack_tactics_browse(api_client):
    resp = api_client.get("/api/v1/attack/tactics")
    assert resp.status_code == 200
    assert resp.get_json()["tactics"] == []


def test_attack_refresh_requires_admin(api_client_factory):
    agent_client, _ = api_client_factory("agent1", "agentpassword123", "agent")
    resp = agent_client.post("/api/v1/attack/refresh")
    assert resp.status_code == 403
