from sqlalchemy import func

from app.models.infrastructure import TARGET_ROLES
from app.models.killchain import STAGE_LABELS, KillChainEntry


def build_graph_payload(engagement):
    nodes = [
        {
            "id": node.id,
            "node_type": node.node_type,
            "name": node.name,
            "role": node.role,
            "category": "target" if node.role in TARGET_ROLES else "attacker",
            "provider": node.provider,
            "region": node.region,
            "notes": node.notes,
        }
        for node in engagement.infrastructure_nodes
    ]

    edges = [
        {
            "id": edge.id,
            "source": edge.source_node_id,
            "target": edge.target_node_id,
            "label": edge.label,
        }
        for edge in engagement.infrastructure_edges
    ]

    order_key = func.coalesce(KillChainEntry.occurred_at, KillChainEntry.created_at)
    entries = (
        KillChainEntry.query.filter_by(engagement_id=engagement.id)
        .order_by(order_key.asc())
        .all()
    )
    killchain = [
        {
            "id": entry.id,
            "stage": entry.stage,
            "stage_label": STAGE_LABELS.get(entry.stage, entry.stage),
            "title": entry.title,
            "description": entry.description,
            "host": entry.host,
            "occurred_at": entry.occurred_at.isoformat() if entry.occurred_at else None,
            "infra_node_id": entry.infra_node_id,
        }
        for entry in entries
    ]

    return {"nodes": nodes, "edges": edges, "killchain": killchain}
