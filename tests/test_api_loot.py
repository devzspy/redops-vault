import io


def _engagement(api_client):
    resp = api_client.post("/api/v1/engagements", json={"name": "E1", "client_name": "Acme"})
    return resp.get_json()["id"]


def test_upload_download_and_delete_loot(api_client):
    eid = _engagement(api_client)
    resp = api_client.post(
        f"/api/v1/engagements/{eid}/loot",
        data={
            "file": (io.BytesIO(b"top secret contents"), "notes.txt"),
            "category": "document",
            "description": "some notes",
            "associated_host": "10.0.0.5",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    loot = resp.get_json()
    assert loot["original_filename"] == "notes.txt"
    assert loot["associated_host"] == "10.0.0.5"
    assert loot["file_size_bytes"] == len(b"top secret contents")

    # Uploading with a new host auto-creates a target infrastructure node.
    nodes = api_client.get(f"/api/v1/engagements/{eid}/targets/nodes").get_json()["nodes"]
    assert any(n["name"] == "10.0.0.5" for n in nodes)

    resp = api_client.get(f"/api/v1/engagements/{eid}/loot")
    assert len(resp.get_json()["files"]) == 1

    resp = api_client.get(f"/api/v1/engagements/{eid}/loot/{loot['id']}/download")
    assert resp.status_code == 200
    assert resp.data == b"top secret contents"

    resp = api_client.patch(f"/api/v1/engagements/{eid}/loot/{loot['id']}", json={"description": "updated"})
    assert resp.get_json()["description"] == "updated"

    resp = api_client.delete(f"/api/v1/engagements/{eid}/loot/{loot['id']}")
    assert resp.status_code == 204


def test_upload_requires_file_and_valid_category(api_client):
    eid = _engagement(api_client)
    resp = api_client.post(f"/api/v1/engagements/{eid}/loot", data={"category": "document"}, content_type="multipart/form-data")
    assert resp.status_code == 400

    resp = api_client.post(
        f"/api/v1/engagements/{eid}/loot",
        data={"file": (io.BytesIO(b"x"), "a.txt"), "category": "bogus"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_credential_masked_by_default_and_revealed_on_demand(api_client):
    eid = _engagement(api_client)
    resp = api_client.post(
        f"/api/v1/engagements/{eid}/credentials",
        json={"username": "jdoe", "password": "hunter2", "credential_type": "password"},
    )
    assert resp.status_code == 201
    cred = resp.get_json()
    assert "secrets" in cred  # create returns the revealed secrets once, like the flash-token pattern
    assert cred["secrets"]["password"] == "hunter2"
    cred_id = cred["id"]

    resp = api_client.get(f"/api/v1/engagements/{eid}/credentials")
    listed = resp.get_json()["credentials"][0]
    assert "secrets" not in listed
    assert listed["has_password"] is True

    resp = api_client.get(f"/api/v1/engagements/{eid}/credentials/{cred_id}")
    assert "secrets" not in resp.get_json()

    resp = api_client.get(f"/api/v1/engagements/{eid}/credentials/{cred_id}?reveal=true")
    assert resp.get_json()["secrets"]["password"] == "hunter2"


def test_credential_invalid_type_is_400(api_client):
    eid = _engagement(api_client)
    resp = api_client.post(
        f"/api/v1/engagements/{eid}/credentials", json={"credential_type": "bitcoin_wallet"}
    )
    assert resp.status_code == 400


def test_credential_totp(api_client):
    eid = _engagement(api_client)
    resp = api_client.post(
        f"/api/v1/engagements/{eid}/credentials",
        json={"username": "svc", "totp_secret": "JBSWY3DPEHPK3PXP"},
    )
    cred_id = resp.get_json()["id"]

    resp = api_client.get(f"/api/v1/engagements/{eid}/credentials/{cred_id}/totp")
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["code"]) == 6

    resp = api_client.delete(f"/api/v1/engagements/{eid}/credentials/{cred_id}")
    assert resp.status_code == 204
