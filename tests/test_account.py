from tests.conftest import csrf_token


def test_admin_reset_forces_password_change_on_next_login(admin_client, second_client):
    csrf = csrf_token(admin_client)
    admin_client.post(
        "/admin/users",
        data={"username": "op1", "password": "operatorpass123", "role": "operator", "csrf_token": csrf},
    )
    with admin_client.application.app_context():
        from app.models.user import User

        user_id = User.query.filter_by(username="op1").first().id

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/admin/users/{user_id}/reset-password",
        data={"password": "newtemppass123", "csrf_token": csrf},
    )

    op_client = second_client
    op_client.post("/login", data={"username": "op1", "password": "newtemppass123"})

    resp = op_client.get("/engagements")
    assert resp.status_code == 302
    assert "/account/password" in resp.headers["Location"]

    resp = op_client.get("/account/password")
    assert resp.status_code == 200


def test_forced_password_change_clears_flag_and_unlocks_app(admin_client, second_client):
    csrf = csrf_token(admin_client)
    admin_client.post(
        "/admin/users",
        data={"username": "op2", "password": "operatorpass123", "role": "operator", "csrf_token": csrf},
    )
    with admin_client.application.app_context():
        from app.models.user import User

        user_id = User.query.filter_by(username="op2").first().id

    csrf = csrf_token(admin_client)
    admin_client.post(
        f"/admin/users/{user_id}/reset-password",
        data={"password": "newtemppass123", "csrf_token": csrf},
    )

    op_client = second_client
    op_client.post("/login", data={"username": "op2", "password": "newtemppass123"})

    csrf = csrf_token(op_client)
    resp = op_client.post(
        "/account/password",
        data={
            "current_password": "newtemppass123",
            "new_password": "brandnewpass456",
            "confirm_password": "brandnewpass456",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302
    assert "/account/password" not in resp.headers["Location"]

    resp = op_client.get("/engagements")
    assert resp.status_code == 200

    with admin_client.application.app_context():
        from app.models.user import User

        user = User.query.filter_by(username="op2").first()
        assert user.must_change_password is False


def test_self_service_password_change_requires_current_password(admin_client):
    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        "/account/password",
        data={
            "current_password": "wrong-password",
            "new_password": "brandnewpass456",
            "confirm_password": "brandnewpass456",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 200
    assert b"Current password is incorrect" in resp.data


def test_self_service_password_change_updates_login_credentials(admin_client):
    csrf = csrf_token(admin_client)
    resp = admin_client.post(
        "/account/password",
        data={
            "current_password": "adminpassword123",
            "new_password": "brandnewpass456",
            "confirm_password": "brandnewpass456",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 302

    fresh_client = admin_client.application.test_client()
    fresh_client.post("/login", data={"username": "admin", "password": "brandnewpass456"})
    assert fresh_client.get("/engagements").status_code == 200
