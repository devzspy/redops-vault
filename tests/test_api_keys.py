from tests.conftest import csrf_token


def _create_key(client, name="my-cli-key"):
    csrf = csrf_token(client)
    return client.post("/api-keys", data={"name": name, "csrf_token": csrf})


def test_create_key_shows_plaintext_once(admin_client):
    resp = _create_key(admin_client, "laptop-cli")
    resp = admin_client.get("/api-keys")
    assert resp.status_code == 200
    assert b"laptop-cli" in resp.data

    with admin_client.application.app_context():
        from app.models.api_key import ApiKey

        keys = ApiKey.query.all()
        assert len(keys) == 1
        assert keys[0].key_hash is not None
        assert len(keys[0].key_hash) == 64


def test_revoke_key(admin_client):
    _create_key(admin_client, "revoke-me")

    with admin_client.application.app_context():
        from app.models.api_key import ApiKey

        key_id = ApiKey.query.filter_by(name="revoke-me").first().id

    csrf = csrf_token(admin_client)
    resp = admin_client.post(f"/api-keys/{key_id}/revoke", data={"csrf_token": csrf})
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.api_key import ApiKey

        key = ApiKey.query.get(key_id)
        assert key.revoked_at is not None
        assert not key.is_active()


def test_cannot_revoke_another_users_key(admin_client, second_client):
    _create_key(admin_client, "admins-key")

    with admin_client.application.app_context():
        from app.models.api_key import ApiKey

        key_id = ApiKey.query.filter_by(name="admins-key").first().id

    csrf = csrf_token(admin_client)
    admin_client.post(
        "/admin/users",
        data={"username": "op2", "password": "operatorpass123", "role": "operator", "csrf_token": csrf},
    )
    second_client.post("/login", data={"username": "op2", "password": "operatorpass123"})
    csrf2 = csrf_token(second_client)
    resp = second_client.post(f"/api-keys/{key_id}/revoke", data={"csrf_token": csrf2})
    assert resp.status_code == 404

    with admin_client.application.app_context():
        from app.models.api_key import ApiKey

        key = ApiKey.query.get(key_id)
        assert key.is_active()
