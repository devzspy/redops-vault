import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_server_script_runs_without_import_error_when_invoked_directly():
    """`python mcp_server/server.py` -- exactly how MCP clients launch it
    per .mcp.json -- puts mcp_server/ itself on sys.path, not its parent,
    so `import mcp_server` fails unless server.py fixes up sys.path itself.
    Feeding it a closed stdin makes the stdio server see EOF and exit
    immediately, so this only checks startup/import, not the protocol.
    """
    env = dict(os.environ, REDOPS_API_KEY="rov_test_dummy_key")
    result = subprocess.run(
        [sys.executable, os.path.join("mcp_server", "server.py")],
        cwd=REPO_ROOT,
        env=env,
        input="",
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert "ModuleNotFoundError" not in result.stderr, result.stderr
    assert "Traceback" not in result.stderr, result.stderr
    assert result.returncode == 0
