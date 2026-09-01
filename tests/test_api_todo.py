def _engagement(api_client):
    resp = api_client.post("/api/v1/engagements", json={"name": "E1", "client_name": "Acme"})
    return resp.get_json()["id"]


def _todo(api_client, eid, title="Do the thing"):
    return api_client.post(f"/api/v1/engagements/{eid}/todos", json={"title": title}).get_json()


def test_claim_handoff_done_reopen_cycle(api_client):
    eid = _engagement(api_client)
    todo = _todo(api_client, eid)
    assert todo["is_available"] is True

    resp = api_client.post(f"/api/v1/engagements/{eid}/todos/{todo['id']}/claim")
    assert resp.get_json()["is_in_progress"] is True

    resp = api_client.post(
        f"/api/v1/engagements/{eid}/todos/{todo['id']}/handoff", json={"handoff_notes": "blocked on creds"}
    )
    body = resp.get_json()
    assert body["is_available"] is True
    assert body["handoff_notes"] == "blocked on creds"

    resp = api_client.post(f"/api/v1/engagements/{eid}/todos/{todo['id']}/done")
    assert resp.get_json()["status"] == "done"

    resp = api_client.post(f"/api/v1/engagements/{eid}/todos/{todo['id']}/reopen")
    assert resp.get_json()["status"] == "open"


def test_cannot_claim_or_handoff_a_done_todo(api_client):
    eid = _engagement(api_client)
    todo = _todo(api_client, eid)
    api_client.post(f"/api/v1/engagements/{eid}/todos/{todo['id']}/done")

    assert api_client.post(f"/api/v1/engagements/{eid}/todos/{todo['id']}/claim").status_code == 400
    assert api_client.post(f"/api/v1/engagements/{eid}/todos/{todo['id']}/handoff").status_code == 400


def test_delete_todo(api_client):
    eid = _engagement(api_client)
    todo = _todo(api_client, eid)
    resp = api_client.delete(f"/api/v1/engagements/{eid}/todos/{todo['id']}")
    assert resp.status_code == 204
    assert api_client.get(f"/api/v1/engagements/{eid}/todos").get_json()["todos"] == []
