from tests.conftest import csrf_token


def _create_engagement(client, name="Acme Corp Q3"):
    csrf = csrf_token(client)
    resp = client.post(
        "/engagements",
        data={"name": name, "client_name": "Acme Corp", "description": "Test engagement", "csrf_token": csrf},
    )
    engagement_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
    return engagement_id


def _set_status(client, engagement_id, status):
    csrf = csrf_token(client)
    return client.post(f"/engagements/{engagement_id}/status", data={"status": status, "csrf_token": csrf})


def _toggle_archive(client, engagement_id):
    csrf = csrf_token(client)
    return client.post(f"/engagements/{engagement_id}/archive", data={"csrf_token": csrf})


def test_create_and_view_engagement(admin_client):
    engagement_id = _create_engagement(admin_client)
    resp = admin_client.get(f"/engagements/{engagement_id}")
    assert resp.status_code == 200
    assert b"Acme Corp Q3" in resp.data


def test_new_engagement_defaults_to_backlog_status(admin_client):
    engagement_id = _create_engagement(admin_client)

    with admin_client.application.app_context():
        from app.models.engagement import Engagement

        engagement = Engagement.query.get(engagement_id)
        assert engagement.status == "backlog"
        assert engagement.is_archived is False


def test_engagement_status_transition(admin_client):
    engagement_id = _create_engagement(admin_client)
    resp = _set_status(admin_client, engagement_id, "completed")
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.engagement import Engagement

        engagement = Engagement.query.get(engagement_id)
        assert engagement.status == "completed"


def test_engagement_can_be_set_to_planning_status(admin_client):
    engagement_id = _create_engagement(admin_client)
    _set_status(admin_client, engagement_id, "planning")

    with admin_client.application.app_context():
        from app.models.engagement import Engagement

        assert Engagement.query.get(engagement_id).status == "planning"


def test_archived_is_not_a_valid_status_value(admin_client):
    engagement_id = _create_engagement(admin_client)
    resp = _set_status(admin_client, engagement_id, "archived")
    assert resp.status_code == 400

    with admin_client.application.app_context():
        from app.models.engagement import Engagement

        assert Engagement.query.get(engagement_id).status == "backlog"


def test_ajax_status_change_returns_json(admin_client):
    engagement_id = _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        f"/engagements/{engagement_id}/status",
        data={"status": "active", "csrf_token": csrf, "ajax": "1"},
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True, "status": "active"}


def test_toggle_archive_flag_preserves_status(admin_client):
    engagement_id = _create_engagement(admin_client)
    _set_status(admin_client, engagement_id, "planning")

    resp = _toggle_archive(admin_client, engagement_id)
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.engagement import Engagement

        engagement = Engagement.query.get(engagement_id)
        assert engagement.is_archived is True
        assert engagement.status == "planning"

    resp = _toggle_archive(admin_client, engagement_id)
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.engagement import Engagement

        engagement = Engagement.query.get(engagement_id)
        assert engagement.is_archived is False
        assert engagement.status == "planning"


def test_default_board_hides_archived_engagements(admin_client):
    visible_id = _create_engagement(admin_client, name="Visible Co")
    archived_id = _create_engagement(admin_client, name="Archived Co")
    _set_status(admin_client, archived_id, "planning")
    _toggle_archive(admin_client, archived_id)

    resp = admin_client.get("/engagements")
    assert resp.status_code == 200
    assert b"Visible Co" in resp.data
    assert b"Archived Co" not in resp.data


def test_show_archived_toggle_reveals_archived_engagement_under_its_status(admin_client):
    archived_id = _create_engagement(admin_client, name="Archived Co")
    _set_status(admin_client, archived_id, "planning")
    _toggle_archive(admin_client, archived_id)

    resp = admin_client.get("/engagements?show_archived=1")
    assert resp.status_code == 200
    assert b"Archived Co" in resp.data


def test_operator_can_see_engagement_created_by_admin(admin_client, second_client):
    _create_engagement(admin_client)
    csrf = csrf_token(admin_client)
    admin_client.post(
        "/admin/users",
        data={"username": "op1", "password": "operatorpass123", "role": "operator", "csrf_token": csrf},
    )
    second_client.post("/login", data={"username": "op1", "password": "operatorpass123"})
    resp = second_client.get("/engagements")
    assert resp.status_code == 200
    assert b"Acme Corp Q3" in resp.data


def test_operator_forbidden_from_admin_routes(admin_client, second_client):
    csrf = csrf_token(admin_client)
    admin_client.post(
        "/admin/users",
        data={"username": "op1", "password": "operatorpass123", "role": "operator", "csrf_token": csrf},
    )
    second_client.post("/login", data={"username": "op1", "password": "operatorpass123"})
    resp = second_client.get("/admin/users")
    assert resp.status_code == 403


def _request_deletion(client, engagement_id):
    csrf = csrf_token(client)
    return client.post(f"/engagements/{engagement_id}/delete/request", data={"csrf_token": csrf})


def _approve_deletion(client, engagement_id):
    csrf = csrf_token(client)
    return client.post(f"/engagements/{engagement_id}/delete/approve", data={"csrf_token": csrf})


def _cancel_deletion(client, engagement_id):
    csrf = csrf_token(client)
    return client.post(f"/engagements/{engagement_id}/delete/cancel", data={"csrf_token": csrf})


def test_deletion_requires_approval_and_is_not_deleted_immediately(admin_client):
    engagement_id = _create_engagement(admin_client)
    resp = _request_deletion(admin_client, engagement_id)
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.engagement import Engagement

        assert Engagement.query.get(engagement_id) is not None


def test_requester_cannot_self_approve_deletion(admin_client):
    engagement_id = _create_engagement(admin_client)
    _request_deletion(admin_client, engagement_id)

    resp = _approve_deletion(admin_client, engagement_id)
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.engagement import Engagement

        assert Engagement.query.get(engagement_id) is not None


def test_second_admin_can_approve_deletion(admin_client, second_client):
    engagement_id = _create_engagement(admin_client)
    _request_deletion(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    admin_client.post(
        "/admin/users",
        data={"username": "admin2", "password": "adminpassword456", "role": "admin", "csrf_token": csrf},
    )
    second_client.post("/login", data={"username": "admin2", "password": "adminpassword456"})

    resp = _approve_deletion(second_client, engagement_id)
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.engagement import Engagement

        assert Engagement.query.get(engagement_id) is None


def test_operator_can_approve_deletion_requested_by_admin(admin_client, second_client):
    engagement_id = _create_engagement(admin_client)
    _request_deletion(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    admin_client.post(
        "/admin/users",
        data={"username": "op1", "password": "operatorpass123", "role": "operator", "csrf_token": csrf},
    )
    second_client.post("/login", data={"username": "op1", "password": "operatorpass123"})

    resp = _approve_deletion(second_client, engagement_id)
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.engagement import Engagement

        assert Engagement.query.get(engagement_id) is None


def test_agent_cannot_approve_deletion(admin_client, second_client):
    engagement_id = _create_engagement(admin_client)
    _request_deletion(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    admin_client.post(
        "/admin/users",
        data={"username": "agent1", "password": "agentpassword123", "role": "agent", "csrf_token": csrf},
    )
    second_client.post("/login", data={"username": "agent1", "password": "agentpassword123"})

    resp = _approve_deletion(second_client, engagement_id)
    assert resp.status_code == 403

    with admin_client.application.app_context():
        from app.models.engagement import Engagement

        assert Engagement.query.get(engagement_id) is not None


def test_operator_cannot_request_deletion(admin_client, second_client):
    engagement_id = _create_engagement(admin_client)

    csrf = csrf_token(admin_client)
    admin_client.post(
        "/admin/users",
        data={"username": "op1", "password": "operatorpass123", "role": "operator", "csrf_token": csrf},
    )
    second_client.post("/login", data={"username": "op1", "password": "operatorpass123"})

    resp = _request_deletion(second_client, engagement_id)
    assert resp.status_code == 403

    with admin_client.application.app_context():
        from app.models.engagement import Engagement

        assert Engagement.query.get(engagement_id) is not None


def test_admin_can_cancel_pending_deletion_request(admin_client):
    engagement_id = _create_engagement(admin_client)
    _request_deletion(admin_client, engagement_id)

    resp = _cancel_deletion(admin_client, engagement_id)
    assert resp.status_code == 302

    with admin_client.application.app_context():
        from app.models.engagement import Engagement

        engagement = Engagement.query.get(engagement_id)
        assert engagement is not None
        assert engagement.deletion_request is None


def test_detail_page_renders_pending_deletion_banner(admin_client, second_client):
    engagement_id = _create_engagement(admin_client)
    _request_deletion(admin_client, engagement_id)

    csrf = csrf_token(admin_client)
    admin_client.post(
        "/admin/users",
        data={"username": "op1", "password": "operatorpass123", "role": "operator", "csrf_token": csrf},
    )
    second_client.post("/login", data={"username": "op1", "password": "operatorpass123"})

    resp = admin_client.get(f"/engagements/{engagement_id}")
    assert resp.status_code == 200
    assert b"Deletion requested" in resp.data
    assert b"Cancel Request" in resp.data
    assert b"Approve" not in resp.data

    resp = second_client.get(f"/engagements/{engagement_id}")
    assert resp.status_code == 200
    assert b"Approve &amp; Delete Permanently" in resp.data
    assert b"Cancel Request" not in resp.data


def test_cannot_request_deletion_twice(admin_client):
    engagement_id = _create_engagement(admin_client)
    _request_deletion(admin_client, engagement_id)
    _request_deletion(admin_client, engagement_id)

    with admin_client.application.app_context():
        from app.models.engagement_deletion_request import EngagementDeletionRequest

        assert EngagementDeletionRequest.query.filter_by(engagement_id=engagement_id).count() == 1
