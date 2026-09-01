from typing import Optional

from mcp_server import client


def register(mcp):
    @mcp.tool()
    def attack_tactics() -> dict:
        """List the MITRE ATT&CK Enterprise matrix (tactics with their
        top-level techniques). Sub-techniques are nested under each technique."""
        return client.get("/attack/tactics")

    @mcp.tool()
    def attack_technique_get(attack_id: str) -> dict:
        """Get one ATT&CK technique by its id (e.g. 'T1566'), including which
        engagements have technique mappings against it."""
        return client.get(f"/attack/techniques/{attack_id}")

    @mcp.tool()
    def attack_refresh() -> dict:
        """Re-sync the local ATT&CK tactic/technique cache from MITRE's public
        STIX feed. Requires an admin-role API key. This makes a live outbound
        request to MITRE's GitHub and can take a while -- use deliberately,
        not as a routine step."""
        return client.post("/attack/refresh")

    @mcp.tool()
    def attack_map_technique_to_loot(engagement_id: int, file_id: int, attack_id: str, notes: Optional[str] = None) -> dict:
        """Map an ATT&CK technique to a loot file as evidence of its use."""
        return client.post(
            f"/engagements/{engagement_id}/loot/{file_id}/map-technique", json={"attack_id": attack_id, "notes": notes}
        )

    @mcp.tool()
    def attack_map_technique_to_killchain(engagement_id: int, entry_id: int, attack_id: str, notes: Optional[str] = None) -> dict:
        """Map an ATT&CK technique to a kill chain entry as evidence of its use."""
        return client.post(
            f"/engagements/{engagement_id}/killchain/{entry_id}/map-technique",
            json={"attack_id": attack_id, "notes": notes},
        )

    @mcp.tool()
    def attack_unmap_technique(mapping_id: int) -> dict:
        """Remove a technique mapping (from either a loot file or a kill chain entry)."""
        return client.delete(f"/technique-mappings/{mapping_id}")
