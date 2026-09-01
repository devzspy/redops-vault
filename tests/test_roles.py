from werkzeug.datastructures import MultiDict

from tests.conftest import csrf_token


def _create_engagement(client, name="Acme Corp Q3"):
    csrf = csrf_token(client)
    resp = client.post(
        "/engagements",
        data={"name": name, "client_name": "Acme Corp", "description": "Test engagement", "csrf_token": csrf},
    )
    return int(resp.headers["Location"].rstrip("/").split("/")[-1])


def _create_user(admin_client, username, password, role):
    csrf = csrf_token(admin_client)
    return admin_client.post(
        "/admin/users",
        data={"username": username, "password": password, "role": role, "csrf_token": csrf},
    )


def _login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


def _assign_engagement(admin_client, user_id, engagement_ids, role="blueteam"):
    csrf = csrf_token(admin_client)
    data = MultiDict([("role", role), ("is_active", "on"), ("csrf_token", csrf)])
    for eid in engagement_ids:
        data.add("engagement_ids", str(eid))
    return admin_client.post(f"/admin/users/{user_id}/edit", data=data)


def _user_id(admin_client, username):
    with admin_client.application.app_context():
        from app.models.user import User

        return User.query.filter_by(username=username).first().id


def test_agent_role_behaves_like_operator(admin_client, second_client):
    _create_user(admin_client, "botty", "agentpassword123", "agent")
    _login(second_client, "botty", "agentpassword123")

    resp = second_client.get("/engagements")
    assert resp.status_code == 200

    with admin_client.application.app_context():
        from app.models.user import User

        user = User.query.filter_by(username="botty").first()
        assert user.role == "agent"
        assert not user.is_admin()


def test_blueteam_sees_no_engagements_until_assigned(admin_client, second_client):
    engagement_id = _create_engagement(admin_client)
    _create_user(admin_client, "watcher", "blueteampass123", "blueteam")
    user_id = _user_id(admin_client, "watcher")

    _login(second_client, "watcher", "blueteampass123")

    resp = second_client.get(f"/engagements/{engagement_id}")
    assert resp.status_code == 403

    list_resp = second_client.get("/engagements")
    assert list_resp.status_code == 200
    assert b"Acme Corp Q3" not in list_resp.data

    _assign_engagement(admin_client, user_id, [engagement_id])

    resp = second_client.get(f"/engagements/{engagement_id}")
    assert resp.status_code == 200

    list_resp = second_client.get("/engagements")
    assert b"Acme Corp Q3" in list_resp.data


def test_blueteam_is_read_only_within_assigned_engagement(admin_client, second_client):
    engagement_id = _create_engagement(admin_client)
    _create_user(admin_client, "watcher2", "blueteampass123", "blueteam")
    user_id = _user_id(admin_client, "watcher2")
    _assign_engagement(admin_client, user_id, [engagement_id])

    _login(second_client, "watcher2", "blueteampass123")
    csrf = csrf_token(second_client)
    resp = second_client.post(
        f"/engagements/{engagement_id}/links",
        data={"url": "https://example.com", "csrf_token": csrf},
    )
    assert resp.status_code == 403


def test_blueteam_cannot_view_unassigned_engagement(admin_client, second_client):
    assigned_id = _create_engagement(admin_client, "Assigned Co")
    other_id = _create_engagement(admin_client, "Other Co")
    user_id = _user_id_after_create(admin_client, "watcher3", "blueteampass123")
    _assign_engagement(admin_client, user_id, [assigned_id])

    _login(second_client, "watcher3", "blueteampass123")
    assert second_client.get(f"/engagements/{assigned_id}").status_code == 200
    assert second_client.get(f"/engagements/{other_id}").status_code == 403


def _user_id_after_create(admin_client, username, password):
    _create_user(admin_client, username, password, "blueteam")
    return _user_id(admin_client, username)


def test_blueteam_blocked_from_admin_and_backups(admin_client, second_client):
    _create_user(admin_client, "watcher4", "blueteampass123", "blueteam")
    _login(second_client, "watcher4", "blueteampass123")

    assert second_client.get("/admin/users").status_code == 403
    assert second_client.get("/backups").status_code == 403
