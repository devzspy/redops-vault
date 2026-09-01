"""RedOps Vault MCP server -- exposes the /api/v1 JSON API as MCP tools so
an AI agent can drive the full engagement lifecycle: engagements, findings,
loot, credentials, kill chain, infrastructure/targets, IOCs, threat model,
todos, and ATT&CK technique mapping. Admin (user management) and Backups
are intentionally not exposed -- they stay human-only, same as the API.

Requires (in the environment):
  REDOPS_API_KEY       Bearer token from /api-keys in the web UI, for an
                        agent/operator/admin-role user.
  REDOPS_API_BASE_URL   Optional, defaults to http://localhost:5000/api/v1

Run directly (stdio transport, the standard local MCP setup):
  python mcp_server/server.py
"""

import os
import sys

# Running this file directly (`python mcp_server/server.py`, which is how
# MCP clients launch it per .mcp.json) puts mcp_server/ itself on sys.path,
# not its parent -- so `import mcp_server` fails without this. Inserting
# the repo root here makes the package importable regardless of whether
# this is run as a script, via `python -m mcp_server.server`, or imported
# normally as a module.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("redops-vault")

from mcp_server.tools import (  # noqa: E402
    activity,
    attack,
    credentials,
    engagements,
    findings,
    infrastructure,
    ioc,
    killchain,
    loot,
    targets,
    threat_model,
    todo,
)

for module in (
    engagements,
    findings,
    loot,
    credentials,
    killchain,
    infrastructure,
    targets,
    ioc,
    threat_model,
    todo,
    attack,
    activity,
):
    module.register(mcp)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
