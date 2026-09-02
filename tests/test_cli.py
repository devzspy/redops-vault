"""CLI tests. Command modules resolve their ApiClient via
cli.commands._util.get_client(ctx) -- monkeypatching that one function point
lets every command run against the real Flask app in-process (via an httpx
WSGITransport) instead of a real socket, without touching CLI config/env.
"""

import httpx
import pytest
from click.testing import CliRunner

from cli.client import ApiClient
from cli.main import cli
from tests.conftest import _issue_api_key


def _api_client(app, token):
    transport = httpx.WSGITransport(app=app.wsgi_app)
    return ApiClient("http://testserver/api/v1", token, transport=transport)


@pytest.fixture
def cli_api(app, admin_client, monkeypatch):
    with app.app_context():
        from app.models.user import User

        user_id = User.query.filter_by(username="admin").first().id
    token = _issue_api_key(app, user_id)
    api = _api_client(app, token)
    monkeypatch.setattr("cli.commands._util.get_client", lambda ctx: api)
    yield api
    api.close()


def run(*args):
    return CliRunner().invoke(cli, list(args))


def test_root_help():
    result = run("--help")
    assert result.exit_code == 0
    assert "engagement" in result.output
    assert "credential" in result.output


def test_missing_api_key_is_a_friendly_error(monkeypatch):
    monkeypatch.delenv("REDOPS_API_KEY", raising=False)
    monkeypatch.setattr("cli.config.load", lambda: {})
    result = run("engagement", "list")
    assert result.exit_code != 0
    assert "No API key configured" in result.output


def test_engagement_create_get_list(cli_api):
    result = run(
        "--json", "engagement", "create", "--name", "Op Nightfall", "--client-name", "Acme Corp",
        "--description", "Initial access assessment",
    )
    assert result.exit_code == 0, result.output
    assert '"name": "Op Nightfall"' in result.output

    result = run("engagement", "list")
    assert result.exit_code == 0, result.output
    assert "Op Nightfall" in result.output
    assert "Acme Corp" in result.output


def test_engagement_update_and_set_status(cli_api):
    create = run("--json", "engagement", "create", "--name", "Op Silent", "--client-name", "Globex")
    engagement_id = __import__("json").loads(create.output)["id"]

    result = run("engagement", "set-status", str(engagement_id), "active")
    assert result.exit_code == 0, result.output
    assert "Active" in result.output

    result = run("--json", "engagement", "update", str(engagement_id), "--description", "Updated scope")
    assert result.exit_code == 0, result.output
    assert "Updated scope" in result.output


def test_finding_and_credential_lifecycle(cli_api):
    import json

    create = run("--json", "engagement", "create", "--name", "Op Ember", "--client-name", "Initech")
    engagement_id = json.loads(create.output)["id"]

    result = run(
        "--json", "finding", "create", "-e", str(engagement_id),
        "--title", "SQL Injection", "--severity", "high", "--details", "Found in login form.",
    )
    assert result.exit_code == 0, result.output
    finding_id = json.loads(result.output)["id"]

    result = run("finding", "list", "-e", str(engagement_id))
    assert result.exit_code == 0
    assert "SQL Injection" in result.output

    result = run("finding", "delete", "-e", str(engagement_id), str(finding_id))
    assert result.exit_code == 0
    assert "Deleted" in result.output

    result = run(
        "--json", "credential", "create", "-e", str(engagement_id),
        "--username", "svc_backup", "--password", "hunter2", "--source-host", "dc01.corp.local",
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["secrets"]["password"] == "hunter2"

    result = run("credential", "list", "-e", str(engagement_id))
    assert result.exit_code == 0
    assert "svc_backup" in result.output
    assert "hunter2" not in result.output  # masked in the non-reveal list view


def test_todo_lifecycle(cli_api):
    import json

    create = run("--json", "engagement", "create", "--name", "Op Ledger", "--client-name", "Umbrella")
    engagement_id = json.loads(create.output)["id"]

    result = run("--json", "todo", "create", "-e", str(engagement_id), "--title", "Enumerate AD")
    todo_id = json.loads(result.output)["id"]

    result = run("todo", "claim", "-e", str(engagement_id), str(todo_id))
    assert result.exit_code == 0
    assert "admin" in result.output

    result = run("todo", "complete", "-e", str(engagement_id), str(todo_id))
    assert result.exit_code == 0


def test_target_node_detail_shows_correlated_records(cli_api):
    import json

    create = run("--json", "engagement", "create", "--name", "Op Correlate", "--client-name", "Hexagon")
    engagement_id = json.loads(create.output)["id"]

    create = run(
        "--json", "target", "node", "create", "-e", str(engagement_id),
        "--type", "hostname", "--name", "dc01.corp.local", "--role", "target",
    )
    node_id = json.loads(create.output)["id"]

    result = run(
        "--json", "credential", "create", "-e", str(engagement_id),
        "--username", "svc_backup", "--password", "hunter2hunter2", "--source-host", "DC01.CORP.LOCAL",
    )
    assert result.exit_code == 0, result.output

    result = run("--json", "target", "node", "detail", "-e", str(engagement_id), str(node_id))
    assert result.exit_code == 0, result.output
    detail = json.loads(result.output)

    assert detail["node"]["name"] == "dc01.corp.local"
    assert len(detail["credentials"]) == 1
    assert detail["credentials"][0]["username"] == "svc_backup"
    assert "secrets" not in detail["credentials"][0]
    assert len(detail["timeline"]) == 1
    assert detail["timeline"][0]["kind"] == "credential"


def test_config_set_and_show(tmp_path, monkeypatch):
    monkeypatch.setattr("cli.config.config_path", lambda: tmp_path / "config.json")
    result = run("config", "set-url", "http://example.local/api/v1")
    assert result.exit_code == 0

    result = run("config", "set-key", "rov_testkey1234567890")
    assert result.exit_code == 0

    result = run("config", "show")
    assert result.exit_code == 0
    assert "http://example.local/api/v1" in result.output
    assert "rov_tes...7890" in result.output
    assert "rov_testkey1234567890" not in result.output
