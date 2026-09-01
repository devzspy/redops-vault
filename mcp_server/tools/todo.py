from typing import Optional

from mcp_server import client


def register(mcp):
    @mcp.tool()
    def todo_list(engagement_id: int) -> dict:
        """List an engagement's task checklist items."""
        return client.get(f"/engagements/{engagement_id}/todos")

    @mcp.tool()
    def todo_create(engagement_id: int, title: str, notes: Optional[str] = None) -> dict:
        """Add a task to an engagement's checklist. New tasks start open and unassigned."""
        return client.post(f"/engagements/{engagement_id}/todos", json={"title": title, "notes": notes})

    @mcp.tool()
    def todo_get(engagement_id: int, todo_id: int) -> dict:
        """Get one task."""
        return client.get(f"/engagements/{engagement_id}/todos/{todo_id}")

    @mcp.tool()
    def todo_claim(engagement_id: int, todo_id: int) -> dict:
        """Claim a task -- assigns it to you (the API key's owning user) and
        clears any handoff notes. Fails if the task is already done."""
        return client.post(f"/engagements/{engagement_id}/todos/{todo_id}/claim")

    @mcp.tool()
    def todo_handoff(engagement_id: int, todo_id: int, handoff_notes: Optional[str] = None) -> dict:
        """Hand off a task -- clears its assignee (making it available again)
        and records handoff notes for whoever picks it up next. Fails if the
        task is already done."""
        return client.post(f"/engagements/{engagement_id}/todos/{todo_id}/handoff", json={"handoff_notes": handoff_notes})

    @mcp.tool()
    def todo_complete(engagement_id: int, todo_id: int) -> dict:
        """Mark a task done."""
        return client.post(f"/engagements/{engagement_id}/todos/{todo_id}/done")

    @mcp.tool()
    def todo_reopen(engagement_id: int, todo_id: int) -> dict:
        """Reopen a completed task. Keeps whoever was assigned when it was
        marked done as the assignee -- claim or hand it off again if needed."""
        return client.post(f"/engagements/{engagement_id}/todos/{todo_id}/reopen")

    @mcp.tool()
    def todo_delete(engagement_id: int, todo_id: int) -> dict:
        """Delete a task."""
        return client.delete(f"/engagements/{engagement_id}/todos/{todo_id}")
