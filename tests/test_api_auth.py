from tests.conftest import csrf_token


def _create_engagement(admin_client, name="Acme Corp Q3"):
    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        "/engagements",
        data={"name": name, "client_name": "Acme Corp", "description": "Test engagement", "csrf_token": csrf},
    )
    return int(resp.headers["Location"].rstrip("/").split("/")[-1])


def test_missing_authorization_header_is_401(admin_client, second_client):
    # admin_client ensures setup has already run (a user exists), so the
    # setup-wizard redirect doesn't mask the auth check below.
    resp = second_client.get("/api/v1/engagements")
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "missing_api_key"


def test_garbage_token_is_401(admin_client, second_client):
    second_client.environ_base["HTTP_AUTHORIZATION"] = "Bearer not-a-real-token"
    resp = second_client.get("/api/v1/engagements")
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "invalid_api_key"


def test_valid_key_authenticates(api_client):
    resp = api_client.get("/api/v1/engagements")
    assert resp.status_code == 200
    assert resp.get_json() == {"engagements": []}


def test_revoked_key_is_rejected(app, api_client):
    resp = api_client.get("/api/v1/engagements")
    assert resp.status_code == 200

    with app.app_context():
        from app.extensions import db
        from app.models.api_key import ApiKey

        key = ApiKey.query.first()
        from datetime import datetime, timezone

        key.revoked_at = datetime.now(timezone.utc)
        db.session.commit()

    resp = api_client.get("/api/v1/engagements")
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "invalid_api_key"


def test_deactivated_users_key_is_rejected(app, api_client):
    with app.app_context():
        from app.extensions import db
        from app.models.user import User

        user = User.query.filter_by(username="admin").first()
        user.is_active = False
        db.session.commit()

    resp = api_client.get("/api/v1/engagements")
    assert resp.status_code == 401


def test_last_used_at_is_stamped_on_use(app, api_client):
    with app.app_context():
        from app.models.api_key import ApiKey

        assert ApiKey.query.first().last_used_at is None

    api_client.get("/api/v1/engagements")

    with app.app_context():
        from app.models.api_key import ApiKey

        assert ApiKey.query.first().last_used_at is not None


def test_blueteam_key_is_read_only(app, api_client_factory):
    watcher_client, _ = api_client_factory("watcher", "blueteampass123", "blueteam")
    resp = watcher_client.post("/api/v1/engagements", json={"name": "x", "client_name": "y"})
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "forbidden"


def test_blueteam_key_blocked_from_unassigned_engagement(admin_client, api_client_factory):
    engagement_id = _create_engagement(admin_client)
    watcher_client, _ = api_client_factory("watcher2", "blueteampass123", "blueteam")

    resp = watcher_client.get(f"/api/v1/engagements/{engagement_id}")
    assert resp.status_code == 403


def test_blueteam_key_allowed_on_assigned_engagement(app, admin_client, api_client_factory):
    engagement_id = _create_engagement(admin_client)
    watcher_client, user_id = api_client_factory("watcher3", "blueteampass123", "blueteam")

    with app.app_context():
        from app.extensions import db
        from app.models.engagement_assignment import EngagementAssignment

        db.session.add(EngagementAssignment(engagement_id=engagement_id, user_id=user_id, assigned_by_id=user_id))
        db.session.commit()

    resp = watcher_client.get(f"/api/v1/engagements/{engagement_id}")
    assert resp.status_code == 200


def test_admin_and_backups_are_not_exposed_over_the_api(api_client):
    assert api_client.get("/api/v1/admin/users").status_code == 404
    assert api_client.get("/api/v1/backups").status_code == 404


def test_agent_role_key_has_full_access(admin_client, api_client_factory):
    agent_client, _ = api_client_factory("botty", "agentpassword123", "agent")
    resp = agent_client.post("/api/v1/engagements", json={"name": "Bot Engagement", "client_name": "Acme"})
    assert resp.status_code == 201
