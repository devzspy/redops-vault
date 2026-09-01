import ipaddress

from sqlalchemy import func

from app.extensions import db
from app.models.infrastructure import NODE_TYPE_HOSTNAME, NODE_TYPE_IP_ADDRESS, ROLE_TARGET, InfrastructureNode
from app.services import activity_service


def resolve_origin_node(engagement_id, origin, actor_id):
    """Resolves a submitted loot-origin host/IP string to a stored
    associated_host value, auto-creating a target-role InfrastructureNode
    for it if one doesn't already exist for this engagement (matched
    case-insensitively by name). Returns None if origin is blank.
    """
    origin = (origin or "").strip()
    if not origin:
        return None

    existing = InfrastructureNode.query.filter(
        InfrastructureNode.engagement_id == engagement_id,
        func.lower(InfrastructureNode.name) == origin.lower(),
    ).first()
    if existing is None:
        try:
            ipaddress.ip_address(origin)
            node_type = NODE_TYPE_IP_ADDRESS
        except ValueError:
            node_type = NODE_TYPE_HOSTNAME
        node = InfrastructureNode(
            engagement_id=engagement_id,
            node_type=node_type,
            name=origin,
            role=ROLE_TARGET,
            added_by_id=actor_id,
        )
        db.session.add(node)
        db.session.flush()
        activity_service.log_activity(
            engagement_id,
            "infrastructure_node",
            "created",
            f"Added infrastructure node '{node.name}' from loot origin",
        )

    return origin
