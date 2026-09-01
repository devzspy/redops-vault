from tests.conftest import csrf_token


def test_login_with_valid_credentials(admin_client):
    resp = admin_client.get("/engagements")
    assert resp.status_code == 200


def test_login_rejects_wrong_password(client):
    client.post(
        "/setup",
        data={
            "username": "admin",
            "password": "adminpassword123",
            "confirm_password": "adminpassword123",
            "infra_mode": "standing",
        },
    )
    resp = client.post("/login", data={"username": "admin", "password": "wrong-password"})
    assert resp.status_code == 200
    resp = client.get("/engagements")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_logout_clears_session(admin_client):
    csrf = csrf_token(admin_client)
    resp = admin_client.post("/logout", data={"csrf_token": csrf})
    assert resp.status_code == 302
    resp = admin_client.get("/engagements")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_state_changing_route_requires_csrf_token(admin_client):
    resp = admin_client.post("/engagements", data={"name": "No CSRF Co", "client_name": "x"})
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]

    with admin_client.application.app_context():
        from app.models.engagement import Engagement

        assert Engagement.query.filter_by(name="No CSRF Co").count() == 0


def test_deactivated_user_session_is_revoked_immediately(admin_client, second_client):
    csrf = csrf_token(admin_client)
    admin_client.post(
        "/admin/users",
        data={"username": "op1", "password": "operatorpass123", "role": "operator", "csrf_token": csrf},
    )
    op_client = second_client
    op_client.post("/login", data={"username": "op1", "password": "operatorpass123"})
    assert op_client.get("/engagements").status_code == 200

    with admin_client.application.app_context():
        from app.extensions import db
        from app.models.user import User

        user = User.query.filter_by(username="op1").first()
        user.is_active = False
        db.session.commit()

    resp = op_client.get("/engagements")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
