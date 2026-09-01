from tests.conftest import csrf_token


def test_root_redirects_to_setup_when_no_users(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/setup" in resp.headers["Location"]


def test_setup_creates_first_admin_and_redirects_to_login(client):
    resp = client.post(
        "/setup",
        data={
            "username": "admin",
            "password": "adminpassword123",
            "confirm_password": "adminpassword123",
            "infra_mode": "standing",
        },
    )
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]

    with client.application.app_context():
        from app.models.app_setting import INFRA_STANDING, AppSetting
        from app.models.user import ROLE_ADMIN, User

        user = User.query.filter_by(username="admin").first()
        assert user is not None
        assert user.role == ROLE_ADMIN
        assert user.is_active

        setting = AppSetting.get()
        assert setting.infra_mode == INFRA_STANDING
        assert setting.engagement_id is None


def test_setup_engagement_infra_creates_engagement_and_links_setting(client):
    resp = client.post(
        "/setup",
        data={
            "username": "admin",
            "password": "adminpassword123",
            "confirm_password": "adminpassword123",
            "infra_mode": "engagement",
            "engagement_name": "Acme Corp Redteam",
        },
    )
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]

    with client.application.app_context():
        from app.models.app_setting import INFRA_ENGAGEMENT, AppSetting
        from app.models.engagement import Engagement

        setting = AppSetting.get()
        assert setting.infra_mode == INFRA_ENGAGEMENT
        assert setting.engagement_id is not None

        engagement = Engagement.query.get(setting.engagement_id)
        assert engagement is not None
        assert engagement.name == "Acme Corp Redteam"


def test_setup_rejects_engagement_infra_without_name(client):
    resp = client.post(
        "/setup",
        data={
            "username": "admin",
            "password": "adminpassword123",
            "confirm_password": "adminpassword123",
            "infra_mode": "engagement",
        },
    )
    assert resp.status_code == 200
    with client.application.app_context():
        from app.models.user import User

        assert User.query.count() == 0


def test_setup_unreachable_once_a_user_exists(client):
    client.post(
        "/setup",
        data={
            "username": "admin",
            "password": "adminpassword123",
            "confirm_password": "adminpassword123",
            "infra_mode": "standing",
        },
    )
    resp = client.get("/setup")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_setup_rejects_mismatched_passwords(client):
    resp = client.post(
        "/setup",
        data={
            "username": "admin",
            "password": "adminpassword123",
            "confirm_password": "somethingelse",
            "infra_mode": "standing",
        },
    )
    assert resp.status_code == 200
    with client.application.app_context():
        from app.models.user import User

        assert User.query.count() == 0


def test_root_redirects_to_login_when_authenticated_user_missing(client):
    client.post(
        "/setup",
        data={
            "username": "admin",
            "password": "adminpassword123",
            "confirm_password": "adminpassword123",
            "infra_mode": "standing",
        },
    )
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
