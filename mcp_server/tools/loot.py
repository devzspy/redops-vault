from typing import Optional

from mcp_server import client


def register(mcp):
    @mcp.tool()
    def loot_list(engagement_id: int, page: int = 1, per_page: int = 20) -> dict:
        """List an engagement's loot file metadata (paginated). Does not
        include file contents -- use loot_download to fetch a file's bytes."""
        return client.get(f"/engagements/{engagement_id}/loot", params={"page": page, "per_page": per_page})

    @mcp.tool()
    def loot_upload(
        engagement_id: int,
        file_path: str,
        category: str,
        description: Optional[str] = None,
        tags: Optional[str] = None,
        associated_host: Optional[str] = None,
    ) -> dict:
        """Upload a local file as loot for an engagement. `file_path` is a path
        on the machine running this MCP server -- the file is read, streamed
        to the server, and encrypted at rest. category is one of: document,
        screenshot, pcap, key_cert, note, other. tags is a comma-separated
        string. associated_host is a hostname/IP -- if it doesn't match an
        existing infrastructure node for this engagement, a new target-role
        node is created for it automatically."""
        return client.upload(
            f"/engagements/{engagement_id}/loot",
            file_path,
            {"category": category, "description": description, "tags": tags, "associated_host": associated_host},
        )

    @mcp.tool()
    def loot_get(engagement_id: int, file_id: int) -> dict:
        """Get metadata for one loot file."""
        return client.get(f"/engagements/{engagement_id}/loot/{file_id}")

    @mcp.tool()
    def loot_download(engagement_id: int, file_id: int, save_path: str) -> dict:
        """Download and decrypt a loot file to a local path on the machine
        running this MCP server. Returns the saved path, size, and sha256
        rather than the file content itself."""
        return client.download(f"/engagements/{engagement_id}/loot/{file_id}/download", save_path)

    @mcp.tool()
    def loot_update(
        engagement_id: int,
        file_id: int,
        category: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[str] = None,
        associated_host: Optional[str] = None,
    ) -> dict:
        """Update a loot file's metadata. Only the fields you pass are changed.
        The file's contents cannot be replaced -- delete and re-upload instead."""
        payload = {
            k: v
            for k, v in {
                "category": category,
                "description": description,
                "tags": tags,
                "associated_host": associated_host,
            }.items()
            if v is not None
        }
        return client.patch(f"/engagements/{engagement_id}/loot/{file_id}", json=payload)

    @mcp.tool()
    def loot_delete(engagement_id: int, file_id: int) -> dict:
        """Delete a loot file, including its encrypted content."""
        return client.delete(f"/engagements/{engagement_id}/loot/{file_id}")
