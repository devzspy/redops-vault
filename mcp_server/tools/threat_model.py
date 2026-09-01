from typing import Optional

from mcp_server import client


def register(mcp):
    @mcp.tool()
    def threat_model_get(engagement_id: int) -> dict:
        """Get an engagement's threat model / attack plan / objectives document."""
        return client.get(f"/engagements/{engagement_id}/threat-model")

    @mcp.tool()
    def threat_model_save(
        engagement_id: int,
        threat_model: Optional[str] = None,
        attack_plan: Optional[str] = None,
        objectives: Optional[str] = None,
    ) -> dict:
        """Save (create or fully overwrite) an engagement's threat model
        document. Each field accepts a small set of HTML tags (p, strong,
        em, ul/ol/li, headings, etc.) or plain text. Omitted fields are
        cleared, not left unchanged -- this replaces the whole document."""
        return client.put(
            f"/engagements/{engagement_id}/threat-model",
            json={"threat_model": threat_model or "", "attack_plan": attack_plan or "", "objectives": objectives or ""},
        )
