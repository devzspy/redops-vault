def test_help_page_requires_login(client):
    resp = client.get("/help/mcp-server")
    assert resp.status_code == 302


def test_help_page_renders_for_logged_in_user(admin_client):
    resp = admin_client.get("/help/mcp-server")
    assert resp.status_code == 200
    assert b"MCP Server" in resp.data
    assert b"REDOPS_API_KEY" in resp.data
    assert b"engagement_create" in resp.data
    assert b"loot_upload" in resp.data
