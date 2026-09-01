def _engagement(api_client):
    resp = api_client.post("/api/v1/engagements", json={"name": "E1", "client_name": "Acme"})
    return resp.get_json()["id"]


def test_create_finding_requires_valid_severity(api_client):
    eid = _engagement(api_client)
    resp = api_client.post(f"/api/v1/engagements/{eid}/findings", json={"title": "SQLi", "severity": "not-real"})
    assert resp.status_code == 400


def test_create_list_get_update_delete_finding(api_client):
    eid = _engagement(api_client)
    resp = api_client.post(
        f"/api/v1/engagements/{eid}/findings",
        json={"title": "SQL Injection", "severity": "high", "details": "<p>Found in login form</p>"},
    )
    assert resp.status_code == 201
    finding = resp.get_json()
    assert finding["severity_label"] == "High"
    assert "Found in login form" in finding["details"]

    resp = api_client.get(f"/api/v1/engagements/{eid}/findings")
    assert len(resp.get_json()["findings"]) == 1

    resp = api_client.get(f"/api/v1/engagements/{eid}/findings/{finding['id']}")
    assert resp.status_code == 200

    resp = api_client.patch(
        f"/api/v1/engagements/{eid}/findings/{finding['id']}", json={"severity": "critical"}
    )
    assert resp.get_json()["severity"] == "critical"

    resp = api_client.delete(f"/api/v1/engagements/{eid}/findings/{finding['id']}")
    assert resp.status_code == 204
    assert api_client.get(f"/api/v1/engagements/{eid}/findings").get_json()["findings"] == []


def test_finding_correlations_link_and_clear(api_client):
    eid = _engagement(api_client)
    ioc_resp = api_client.post(f"/api/v1/engagements/{eid}/iocs", json={"host": "evil.com"})
    ioc_id = ioc_resp.get_json()["id"]

    resp = api_client.post(
        f"/api/v1/engagements/{eid}/findings",
        json={"title": "F", "severity": "low", "ioc_ids": [ioc_id]},
    )
    finding = resp.get_json()
    assert len(finding["iocs"]) == 1
    assert finding["iocs"][0]["id"] == ioc_id

    resp = api_client.patch(f"/api/v1/engagements/{eid}/findings/{finding['id']}", json={"ioc_ids": []})
    assert resp.get_json()["iocs"] == []


def test_report_markdown_export(api_client):
    eid = _engagement(api_client)
    api_client.post(f"/api/v1/engagements/{eid}/findings", json={"title": "F", "severity": "medium"})
    resp = api_client.get(f"/api/v1/engagements/{eid}/findings/report.md")
    assert resp.status_code == 200
    assert resp.mimetype == "text/markdown"
    assert b"# Findings Report" in resp.data
