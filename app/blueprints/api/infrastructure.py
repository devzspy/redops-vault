from flask import Blueprint, abort, jsonify

from app.auth_utils import current_api_user
from app.blueprints.api import serializers
from app.blueprints.api._common import json_body, require_choice, require_fields, str_or_none
from app.extensions import db
from app.models.engagement import Engagement
from app.models.infrastructure import (
    ATTACKER_ROLES,
    INFRA_STATUSES,
    NODE_TYPES,
    TARGET_ROLES,
    InfrastructureEdge,
    InfrastructureNode,
    InfrastructureService,
)
from app.services import activity_service, network_service

bp = Blueprint(
    "api_infrastructure", __name__, url_prefix="/api/v1/engagements/<int:engagement_id>/infrastructure"
)


def _attacker_nodes_query(engagement_id):
    return InfrastructureNode.query.filter_by(engagement_id=engagement_id).filter(
        db.or_(InfrastructureNode.role.is_(None), InfrastructureNode.role.notin_(TARGET_ROLES))
    )


@bp.route("/nodes", methods=["GET"])
def list_nodes(engagement_id):
    Engagement.query.get_or_404(engagement_id)
    nodes = (
        _attacker_nodes_query(engagement_id)
        .order_by(InfrastructureNode.node_type.asc(), InfrastructureNode.name.asc())
        .all()
    )
    return jsonify(nodes=[serializers.infra_node_dict(n) for n in nodes])


@bp.route("/nodes", methods=["POST"])
def create_node(engagement_id):
    Engagement.query.get_or_404(engagement_id)
    data = json_body()
    require_fields(data, "node_type", "name")
    require_choice(data["node_type"], NODE_TYPES, "node_type")

    role = data.get("role") or None
    if role and role not in ATTACKER_ROLES:
        abort(400, description="Invalid role")
    status = data.get("status") or None
    if status and status not in INFRA_STATUSES:
        abort(400, description="Invalid status")

    node = InfrastructureNode(
        engagement_id=engagement_id,
        node_type=data["node_type"],
        name=data["name"].strip(),
        role=role,
        status=status,
        provider=str_or_none(data.get("provider")),
        region=str_or_none(data.get("region")),
        notes=str_or_none(data.get("notes")),
        added_by_id=current_api_user().id,
    )
    db.session.add(node)
    db.session.flush()
    activity_service.log_activity(engagement_id, "infrastructure_node", "created", f"Added infrastructure node '{node.name}'")
    db.session.commit()
    return jsonify(serializers.infra_node_dict(node)), 201


@bp.route("/nodes/<int:node_id>", methods=["GET"])
def get_node(engagement_id, node_id):
    node = _attacker_nodes_query(engagement_id).filter(InfrastructureNode.id == node_id).first_or_404()
    return jsonify(serializers.infra_node_dict(node))


@bp.route("/nodes/<int:node_id>", methods=["PATCH"])
def update_node(engagement_id, node_id):
    node = InfrastructureNode.query.filter_by(id=node_id, engagement_id=engagement_id).first_or_404()
    if node.role in TARGET_ROLES:
        abort(404)
    data = json_body()

    if "node_type" in data:
        require_choice(data.get("node_type"), NODE_TYPES, "node_type")
        node.node_type = data["node_type"]
    if "name" in data:
        name = str_or_none(data.get("name"))
        if not name:
            abort(400, description="name cannot be blank")
        node.name = name
    if "role" in data:
        role = data.get("role") or None
        if role and role not in ATTACKER_ROLES:
            abort(400, description="Invalid role")
        node.role = role
    if "status" in data:
        status = data.get("status") or None
        if status and status not in INFRA_STATUSES:
            abort(400, description="Invalid status")
        node.status = status
    if "provider" in data:
        node.provider = str_or_none(data.get("provider"))
    if "region" in data:
        node.region = str_or_none(data.get("region"))
    if "notes" in data:
        node.notes = str_or_none(data.get("notes"))

    activity_service.log_activity(engagement_id, "infrastructure_node", "updated", f"Updated infrastructure node '{node.name}'")
    db.session.commit()
    return jsonify(serializers.infra_node_dict(node))


@bp.route("/nodes/<int:node_id>", methods=["DELETE"])
def delete_node(engagement_id, node_id):
    node = InfrastructureNode.query.filter_by(id=node_id, engagement_id=engagement_id).first_or_404()
    activity_service.log_activity(engagement_id, "infrastructure_node", "deleted", f"Deleted infrastructure node '{node.name}'")
    db.session.delete(node)
    db.session.commit()
    return "", 204


@bp.route("/nodes/<int:node_id>/services", methods=["POST"])
def create_service(engagement_id, node_id):
    node = InfrastructureNode.query.filter_by(id=node_id, engagement_id=engagement_id).first_or_404()
    data = json_body()
    require_fields(data, "name")

    port = data.get("port")
    if port is not None and port != "":
        try:
            port = int(port)
        except (TypeError, ValueError):
            abort(400, description="Port must be a number")
    else:
        port = None

    service = InfrastructureService(node_id=node.id, name=data["name"].strip(), port=port)
    db.session.add(service)
    activity_service.log_activity(
        engagement_id, "infrastructure_service", "created", f"Added service '{service.display()}' to '{node.name}'"
    )
    db.session.commit()
    return jsonify({"id": service.id, "name": service.name, "port": service.port, "display": service.display()}), 201


@bp.route("/services/<int:service_id>", methods=["DELETE"])
def delete_service(engagement_id, service_id):
    service = (
        InfrastructureService.query.join(InfrastructureNode)
        .filter(InfrastructureService.id == service_id, InfrastructureNode.engagement_id == engagement_id)
        .first_or_404()
    )
    node = service.node
    activity_service.log_activity(
        engagement_id, "infrastructure_service", "deleted", f"Removed service '{service.display()}' from '{node.name}'"
    )
    db.session.delete(service)
    db.session.commit()
    return "", 204


def _resolve_edge_nodes(engagement_id, data):
    source_id = data.get("source_node_id")
    target_id = data.get("target_node_id")
    if not source_id or not target_id:
        abort(400, description="source_node_id and target_node_id are required")
    if source_id == target_id:
        abort(400, description="Source and target must be different nodes")

    source = InfrastructureNode.query.filter_by(id=source_id, engagement_id=engagement_id).first()
    target = InfrastructureNode.query.filter_by(id=target_id, engagement_id=engagement_id).first()
    if source is None or target is None:
        abort(400, description="Invalid source or target node")
    if source.role in TARGET_ROLES or target.role in TARGET_ROLES:
        abort(400, description="Source and target must both be attacker-owned infrastructure nodes")
    return source_id, target_id


@bp.route("/edges", methods=["GET"])
def list_edges(engagement_id):
    Engagement.query.get_or_404(engagement_id)
    edges = InfrastructureEdge.query.filter_by(engagement_id=engagement_id).all()
    edges = [e for e in edges if e.source_node.role not in TARGET_ROLES and e.target_node.role not in TARGET_ROLES]
    return jsonify(edges=[serializers.infra_edge_dict(e) for e in edges])


@bp.route("/edges", methods=["POST"])
def create_edge(engagement_id):
    Engagement.query.get_or_404(engagement_id)
    data = json_body()
    source_id, target_id = _resolve_edge_nodes(engagement_id, data)

    edge = InfrastructureEdge(
        engagement_id=engagement_id,
        source_node_id=source_id,
        target_node_id=target_id,
        label=str_or_none(data.get("label")),
        notes=str_or_none(data.get("notes")),
        added_by_id=current_api_user().id,
    )
    db.session.add(edge)
    db.session.flush()
    activity_service.log_activity(
        engagement_id, "infrastructure_edge", "created", f"Added network path '{edge.source_node.name}' → '{edge.target_node.name}'"
    )
    db.session.commit()
    return jsonify(serializers.infra_edge_dict(edge)), 201


@bp.route("/edges/<int:edge_id>", methods=["PATCH"])
def update_edge(engagement_id, edge_id):
    edge = InfrastructureEdge.query.filter_by(id=edge_id, engagement_id=engagement_id).first_or_404()
    if edge.source_node.role in TARGET_ROLES or edge.target_node.role in TARGET_ROLES:
        abort(404)
    data = json_body()

    if "source_node_id" in data or "target_node_id" in data:
        source_id, target_id = _resolve_edge_nodes(
            engagement_id,
            {
                "source_node_id": data.get("source_node_id", edge.source_node_id),
                "target_node_id": data.get("target_node_id", edge.target_node_id),
            },
        )
        edge.source_node_id = source_id
        edge.target_node_id = target_id
    if "label" in data:
        edge.label = str_or_none(data.get("label"))
    if "notes" in data:
        edge.notes = str_or_none(data.get("notes"))

    activity_service.log_activity(
        engagement_id, "infrastructure_edge", "updated", f"Updated network path '{edge.source_node.name}' → '{edge.target_node.name}'"
    )
    db.session.commit()
    return jsonify(serializers.infra_edge_dict(edge))


@bp.route("/edges/<int:edge_id>", methods=["DELETE"])
def delete_edge(engagement_id, edge_id):
    edge = InfrastructureEdge.query.filter_by(id=edge_id, engagement_id=engagement_id).first_or_404()
    activity_service.log_activity(
        engagement_id, "infrastructure_edge", "deleted", f"Deleted network path '{edge.source_node.name}' → '{edge.target_node.name}'"
    )
    db.session.delete(edge)
    db.session.commit()
    return "", 204


@bp.route("/graph.json", methods=["GET"])
def graph_json(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return jsonify(network_service.build_graph_payload(engagement))
