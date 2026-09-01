import importlib
import sys

import pytest


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_FILENAME", "test.db")

    import config

    importlib.reload(config)
    config.Config.INSTANCE_DIR = str(tmp_path)
    config.Config.SQLALCHEMY_DATABASE_URI = "sqlite:///" + str(tmp_path / "test.db")
    config.Config.ENCRYPTION_KEY_PATH = str(tmp_path / "encryption.key")
    config.Config.JWT_COOKIE_CSRF_PROTECT = True
    config.Config.JWT_CSRF_CHECK_FORM = True

    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]

    from app import create_app

    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def csrf_token(test_client):
    for (_domain, _path, name), cookie in test_client._cookies.items():
        if "csrf" in name.lower() and "refresh" not in name.lower():
            return cookie.value
    return None


@pytest.fixture
def second_client(app):
    return app.test_client()


@pytest.fixture
def admin_client(client):
    client.post(
        "/setup",
        data={
            "username": "admin",
            "password": "adminpassword123",
            "confirm_password": "adminpassword123",
            "infra_mode": "standing",
        },
    )
    client.post("/login", data={"username": "admin", "password": "adminpassword123"})
    return client


def _issue_api_key(app, user_id, name="test-key"):
    with app.app_context():
        from app.extensions import db
        from app.models.api_key import ApiKey
        from app.services import api_key_service

        token, key_hash, key_prefix = api_key_service.generate_key()
        db.session.add(ApiKey(user_id=user_id, name=name, key_hash=key_hash, key_prefix=key_prefix))
        db.session.commit()
        return token


def _bearer_client(app, token):
    api_test_client = app.test_client()
    api_test_client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return api_test_client


@pytest.fixture
def api_client(app, admin_client):
    """A test client authenticated as the admin user's API key -- admin has
    full access to everything /api/v1 exposes (same as operator/agent),
    so this is the default client for exercising API CRUD.
    """
    with app.app_context():
        from app.models.user import User

        user_id = User.query.filter_by(username="admin").first().id
    token = _issue_api_key(app, user_id)
    return _bearer_client(app, token)


@pytest.fixture
def api_client_factory(app, admin_client):
    """Returns a function(username, password, role) -> test client
    authenticated with a freshly issued API key for a newly created user of
    that role. Used for exercising role-scoped API behavior (e.g. blueteam).
    """

    def _make(username, password, role):
        csrf = csrf_token(admin_client)
        admin_client.post(
            "/admin/users",
            data={"username": username, "password": password, "role": role, "csrf_token": csrf},
        )
        with app.app_context():
            from app.models.user import User

            user_id = User.query.filter_by(username=username).first().id
        token = _issue_api_key(app, user_id)
        return _bearer_client(app, token), user_id

    return _make
