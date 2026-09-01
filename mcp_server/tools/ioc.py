from typing import Optional

from mcp_server import client


def register(mcp):
    @mcp.tool()
    def ioc_list(engagement_id: int) -> dict:
        """List an engagement's indicators of compromise (dropped files, hosts, hashes)."""
        return client.get(f"/engagements/{engagement_id}/iocs")

    @mcp.tool()
    def ioc_create(
        engagement_id: int,
        host: Optional[str] = None,
        location: Optional[str] = None,
        hash_type: Optional[str] = None,
        hash_value: Optional[str] = None,
        dropped_at: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """Record an IOC. hash_type is 'md5' or 'sha256' (omit if not a
        file-based IOC). dropped_at is an ISO 8601 datetime."""
        return client.post(
            f"/engagements/{engagement_id}/iocs",
            json={
                "host": host,
                "location": location,
                "hash_type": hash_type,
                "hash_value": hash_value,
                "dropped_at": dropped_at,
                "notes": notes,
            },
        )

    @mcp.tool()
    def ioc_get(engagement_id: int, ioc_id: int) -> dict:
        """Get one IOC."""
        return client.get(f"/engagements/{engagement_id}/iocs/{ioc_id}")

    @mcp.tool()
    def ioc_update(
        engagement_id: int,
        ioc_id: int,
        host: Optional[str] = None,
        location: Optional[str] = None,
        hash_type: Optional[str] = None,
        hash_value: Optional[str] = None,
        dropped_at: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """Update an IOC. Only the fields you pass are changed."""
        payload = {
            k: v
            for k, v in {
                "host": host,
                "location": location,
                "hash_type": hash_type,
                "hash_value": hash_value,
                "dropped_at": dropped_at,
                "notes": notes,
            }.items()
            if v is not None
        }
        return client.patch(f"/engagements/{engagement_id}/iocs/{ioc_id}", json=payload)

    @mcp.tool()
    def ioc_delete(engagement_id: int, ioc_id: int) -> dict:
        """Delete an IOC."""
        return client.delete(f"/engagements/{engagement_id}/iocs/{ioc_id}")
