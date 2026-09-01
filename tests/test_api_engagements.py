def _create(api_client, name="Acme Corp Q3"):
    resp = api_client.post("/api/v1/engagements", json={"name": name, "client_name": "Acme Corp"})
    assert resp.status_code == 201
    return resp.get_json()


def test_create_and_get_engagement(api_client):
    data = _create(api_client)
    assert data["name"] == "Acme Corp Q3"
    assert data["status"] == "backlog"
    assert data["threat_model"] is None
    assert data["loot_files_count"] == 0

    resp = api_client.get(f"/api/v1/engagements/{data['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["id"] == data["id"]


def test_create_missing_fields_is_400(api_client):
    resp = api_client.post("/api/v1/engagements", json={"name": "no client name"})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


def test_list_excludes_archived_by_default(api_client):
    data = _create(api_client)
    api_client.post(f"/api/v1/engagements/{data['id']}/archive")

    resp = api_client.get("/api/v1/engagements")
    assert resp.get_json()["engagements"] == []

    resp = api_client.get("/api/v1/engagements?show_archived=1")
    assert len(resp.get_json()["engagements"]) == 1


def test_patch_updates_partial_fields(api_client):
    data = _create(api_client)
    resp = api_client.patch(f"/api/v1/engagements/{data['id']}", json={"description": "updated desc"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["description"] == "updated desc"
    assert body["name"] == "Acme Corp Q3"


def test_status_change_rejects_invalid_status(api_client):
    data = _create(api_client)
    resp = api_client.post(f"/api/v1/engagements/{data['id']}/status", json={"status": "not-a-status"})
    assert resp.status_code == 400


def test_status_change_valid(api_client):
    data = _create(api_client)
    resp = api_client.post(f"/api/v1/engagements/{data['id']}/status", json={"status": "active"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "active"


def test_links_crud(api_client):
    data = _create(api_client)
    eid = data["id"]

    resp = api_client.post(f"/api/v1/engagements/{eid}/links", json={"url": "https://example.com", "label": "notes"})
    assert resp.status_code == 201
    link = resp.get_json()
    assert link["url"] == "https://example.com"

    resp = api_client.get(f"/api/v1/engagements/{eid}/links")
    assert len(resp.get_json()["links"]) == 1

    resp = api_client.patch(f"/api/v1/engagements/{eid}/links/{link['id']}", json={"label": "renamed"})
    assert resp.get_json()["label"] == "renamed"

    resp = api_client.delete(f"/api/v1/engagements/{eid}/links/{link['id']}")
    assert resp.status_code == 204
    assert api_client.get(f"/api/v1/engagements/{eid}/links").get_json()["links"] == []


def test_unknown_engagement_is_404(api_client):
    resp = api_client.get("/api/v1/engagements/999999")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "not_found"
