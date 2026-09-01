from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import jwt_required

from app.auth_utils import csrf_protect, current_user
from app.blueprints.infrastructure import bp
from app.extensions import db
from app.models.engagement import Engagement
from app.models.infrastructure import (
    ATTACKER_ROLES,
    INFRA_STATUSES,
    NODE_TYPES,
    TARGET_NODE_TYPES,
    TARGET_ROLES,
    InfrastructureEdge,
    InfrastructureNode,
    InfrastructureService,
)
from app.services import activity_service, network_service


def _node_edit_redirect(engagement_id, node):
    if node.role in TARGET_ROLES:
        return url_for("targets.edit_target_form", engagement_id=engagement_id, node_id=node.id)
    return url_for("infrastructure.edit_node_form", engagement_id=engagement_id, node_id=node.id)


def _attacker_nodes(engagement_id):
    return (
        InfrastructureNode.query.filter_by(engagement_id=engagement_id)
        .filter(
            db.or_(
                InfrastructureNode.role.is_(None),
                InfrastructureNode.role.notin_(TARGET_ROLES),
            )
        )
        .order_by(InfrastructureNode.node_type.asc(), InfrastructureNode.name.asc())
        .all()
    )


def _attacker_edges(engagement_id):
    edges = InfrastructureEdge.query.filter_by(engagement_id=engagement_id).all()
    return [e for e in edges if e.source_node.role not in TARGET_ROLES and e.target_node.role not in TARGET_ROLES]


@bp.route("/engagements/<int:engagement_id>/infrastructure")
@jwt_required()
def list_infrastructure(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return render_template(
        "infrastructure/list.html",
        engagement=engagement,
        nodes=_attacker_nodes(engagement_id),
        edges=_attacker_edges(engagement_id),
    )


@bp.route("/engagements/<int:engagement_id>/infrastructure/nodes/new")
@jwt_required()
def new_node_form(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return render_template(
        "infrastructure/node_form.html",
        engagement=engagement,
        node=None,
        node_types=NODE_TYPES,
        roles=ATTACKER_ROLES,
        infra_statuses=INFRA_STATUSES,
    )


@bp.route("/engagements/<int:engagement_id>/infrastructure/nodes", methods=["POST"])
@csrf_protect
def create_node(engagement_id):
    Engagement.query.get_or_404(engagement_id)

    node_type = request.form.get("node_type")
    name = request.form.get("name", "").strip()
    if node_type not in NODE_TYPES or not name:
        flash("Type and name are required.", "danger")
        return redirect(url_for("infrastructure.new_node_form", engagement_id=engagement_id))

    role = request.form.get("role") or None
    if role and role not in ATTACKER_ROLES:
        abort(400, description="Invalid role")

    status = request.form.get("status") or None
    if status and status not in INFRA_STATUSES:
        abort(400, description="Invalid status")

    node = InfrastructureNode(
        engagement_id=engagement_id,
        node_type=node_type,
        name=name,
        role=role,
        status=status,
        provider=request.form.get("provider", "").strip() or None,
        region=request.form.get("region", "").strip() or None,
        notes=request.form.get("notes", "").strip() or None,
        added_by_id=int(current_user().id),
    )
    db.session.add(node)
    db.session.flush()
    activity_service.log_activity(
        engagement_id, "infrastructure_node", "created", f"Added infrastructure node '{node.name}'"
    )
    db.session.commit()
    flash("Infrastructure node added.", "success")
    return redirect(url_for("infrastructure.list_infrastructure", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/infrastructure/nodes/<int:node_id>/edit")
@jwt_required()
def edit_node_form(engagement_id, node_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    node = InfrastructureNode.query.filter_by(id=node_id, engagement_id=engagement_id).first_or_404()
    if node.role in TARGET_ROLES:
        return redirect(url_for("targets.edit_target_form", engagement_id=engagement_id, node_id=node_id))
    return render_template(
        "infrastructure/node_form.html",
        engagement=engagement,
        node=node,
        node_types=NODE_TYPES,
        roles=ATTACKER_ROLES,
        infra_statuses=INFRA_STATUSES,
    )


@bp.route("/engagements/<int:engagement_id>/infrastructure/nodes/<int:node_id>/edit", methods=["POST"])
@csrf_protect
def edit_node(engagement_id, node_id):
    node = InfrastructureNode.query.filter_by(id=node_id, engagement_id=engagement_id).first_or_404()
    if node.role in TARGET_ROLES:
        abort(404)

    node_type = request.form.get("node_type")
    name = request.form.get("name", "").strip()
    if node_type not in NODE_TYPES or not name:
        flash("Type and name are required.", "danger")
        return redirect(url_for("infrastructure.edit_node_form", engagement_id=engagement_id, node_id=node_id))

    role = request.form.get("role") or None
    if role and role not in ATTACKER_ROLES:
        abort(400, description="Invalid role")

    status = request.form.get("status") or None
    if status and status not in INFRA_STATUSES:
        abort(400, description="Invalid status")

    node.node_type = node_type
    node.name = name
    node.role = role
    node.status = status
    node.provider = request.form.get("provider", "").strip() or None
    node.region = request.form.get("region", "").strip() or None
    node.notes = request.form.get("notes", "").strip() or None
    activity_service.log_activity(
        engagement_id, "infrastructure_node", "updated", f"Updated infrastructure node '{node.name}'"
    )
    db.session.commit()
    flash("Infrastructure node updated.", "success")
    return redirect(url_for("infrastructure.list_infrastructure", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/infrastructure/nodes/<int:node_id>/delete", methods=["POST"])
@csrf_protect
def delete_node(engagement_id, node_id):
    node = InfrastructureNode.query.filter_by(id=node_id, engagement_id=engagement_id).first_or_404()
    activity_service.log_activity(
        engagement_id, "infrastructure_node", "deleted", f"Deleted infrastructure node '{node.name}'"
    )
    db.session.delete(node)
    db.session.commit()
    flash("Infrastructure node deleted.", "success")
    return redirect(url_for("infrastructure.list_infrastructure", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/infrastructure/nodes/<int:node_id>/services", methods=["POST"])
@csrf_protect
def create_service(engagement_id, node_id):
    node = InfrastructureNode.query.filter_by(id=node_id, engagement_id=engagement_id).first_or_404()

    name = request.form.get("name", "").strip()
    if not name:
        flash("Service name is required.", "danger")
        return redirect(_node_edit_redirect(engagement_id, node))

    port = request.form.get("port", type=int)
    if request.form.get("port", "").strip() and port is None:
        flash("Port must be a number.", "danger")
        return redirect(_node_edit_redirect(engagement_id, node))

    service = InfrastructureService(node_id=node.id, name=name, port=port)
    db.session.add(service)
    activity_service.log_activity(
        engagement_id,
        "infrastructure_service",
        "created",
        f"Added service '{service.display()}' to '{node.name}'",
    )
    db.session.commit()
    flash("Service added.", "success")
    return redirect(_node_edit_redirect(engagement_id, node))


@bp.route(
    "/engagements/<int:engagement_id>/infrastructure/nodes/<int:node_id>/services/<int:service_id>/delete",
    methods=["POST"],
)
@csrf_protect
def delete_service(engagement_id, node_id, service_id):
    node = InfrastructureNode.query.filter_by(id=node_id, engagement_id=engagement_id).first_or_404()
    service = InfrastructureService.query.filter_by(id=service_id, node_id=node_id).first_or_404()
    activity_service.log_activity(
        engagement_id,
        "infrastructure_service",
        "deleted",
        f"Removed service '{service.display()}' from '{node.name}'",
    )
    db.session.delete(service)
    db.session.commit()
    flash("Service removed.", "success")
    return redirect(_node_edit_redirect(engagement_id, node))


def _resolve_edge_nodes(engagement_id, redirect_endpoint, **redirect_kwargs):
    """Validates source/target node ids from the submitted edge form.
    Returns (source_id, target_id) on success, or a redirect response to
    send back to the caller when validation fails.
    """
    source_id = request.form.get("source_node_id", type=int)
    target_id = request.form.get("target_node_id", type=int)

    if not source_id or not target_id:
        flash("Source and target nodes are required.", "danger")
        return None, None, redirect(url_for(redirect_endpoint, engagement_id=engagement_id, **redirect_kwargs))
    if source_id == target_id:
        flash("Source and target must be different nodes.", "danger")
        return None, None, redirect(url_for(redirect_endpoint, engagement_id=engagement_id, **redirect_kwargs))

    source = InfrastructureNode.query.filter_by(id=source_id, engagement_id=engagement_id).first()
    target = InfrastructureNode.query.filter_by(id=target_id, engagement_id=engagement_id).first()
    if source is None or target is None:
        abort(400, description="Invalid source or target node")
    if source.role in TARGET_ROLES or target.role in TARGET_ROLES:
        abort(400, description="Source and target must both be attacker-owned infrastructure nodes")

    return source_id, target_id, None


@bp.route("/engagements/<int:engagement_id>/infrastructure/edges/new")
@jwt_required()
def new_edge_form(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return render_template(
        "infrastructure/edge_form.html", engagement=engagement, nodes=_attacker_nodes(engagement_id), edge=None
    )


@bp.route("/engagements/<int:engagement_id>/infrastructure/edges", methods=["POST"])
@csrf_protect
def create_edge(engagement_id):
    Engagement.query.get_or_404(engagement_id)

    source_id, target_id, error_response = _resolve_edge_nodes(engagement_id, "infrastructure.new_edge_form")
    if error_response is not None:
        return error_response

    edge = InfrastructureEdge(
        engagement_id=engagement_id,
        source_node_id=source_id,
        target_node_id=target_id,
        label=request.form.get("label", "").strip() or None,
        notes=request.form.get("notes", "").strip() or None,
        added_by_id=int(current_user().id),
    )
    db.session.add(edge)
    db.session.flush()
    activity_service.log_activity(
        engagement_id,
        "infrastructure_edge",
        "created",
        f"Added network path '{edge.source_node.name}' → '{edge.target_node.name}'",
    )
    db.session.commit()
    flash("Network path added.", "success")
    return redirect(url_for("infrastructure.list_infrastructure", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/infrastructure/edges/<int:edge_id>/edit")
@jwt_required()
def edit_edge_form(engagement_id, edge_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    edge = InfrastructureEdge.query.filter_by(id=edge_id, engagement_id=engagement_id).first_or_404()
    if edge.source_node.role in TARGET_ROLES or edge.target_node.role in TARGET_ROLES:
        return redirect(url_for("targets.edit_edge_form", engagement_id=engagement_id, edge_id=edge_id))
    return render_template(
        "infrastructure/edge_form.html", engagement=engagement, nodes=_attacker_nodes(engagement_id), edge=edge
    )


@bp.route("/engagements/<int:engagement_id>/infrastructure/edges/<int:edge_id>/edit", methods=["POST"])
@csrf_protect
def edit_edge(engagement_id, edge_id):
    edge = InfrastructureEdge.query.filter_by(id=edge_id, engagement_id=engagement_id).first_or_404()
    if edge.source_node.role in TARGET_ROLES or edge.target_node.role in TARGET_ROLES:
        abort(404)

    source_id, target_id, error_response = _resolve_edge_nodes(
        engagement_id, "infrastructure.edit_edge_form", edge_id=edge_id
    )
    if error_response is not None:
        return error_response

    edge.source_node_id = source_id
    edge.target_node_id = target_id
    edge.label = request.form.get("label", "").strip() or None
    edge.notes = request.form.get("notes", "").strip() or None
    activity_service.log_activity(
        engagement_id,
        "infrastructure_edge",
        "updated",
        f"Updated network path '{edge.source_node.name}' → '{edge.target_node.name}'",
    )
    db.session.commit()
    flash("Network path updated.", "success")
    return redirect(url_for("infrastructure.list_infrastructure", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/infrastructure/edges/<int:edge_id>/delete", methods=["POST"])
@csrf_protect
def delete_edge(engagement_id, edge_id):
    edge = InfrastructureEdge.query.filter_by(id=edge_id, engagement_id=engagement_id).first_or_404()
    activity_service.log_activity(
        engagement_id,
        "infrastructure_edge",
        "deleted",
        f"Deleted network path '{edge.source_node.name}' → '{edge.target_node.name}'",
    )
    db.session.delete(edge)
    db.session.commit()
    flash("Network path deleted.", "success")
    return redirect(url_for("infrastructure.list_infrastructure", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/infrastructure/graph.json")
@jwt_required()
def graph_json(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return jsonify(network_service.build_graph_payload(engagement))


@bp.route("/engagements/<int:engagement_id>/network")
@jwt_required()
def network_map(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return render_template("network/map.html", engagement=engagement)


@bp.route("/engagements/<int:engagement_id>/network/g6")
@jwt_required()
def network_map_g6(engagement_id):
    """Experimental G6-based renderer for the same graph.json data, kept
    alongside the Cytoscape-based network_map view for side-by-side
    comparison rather than replacing it.
    """
    engagement = Engagement.query.get_or_404(engagement_id)
    return render_template("network/map_g6.html", engagement=engagement)


@bp.route("/engagements/<int:engagement_id>/attack-map")
@jwt_required()
def attack_map(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return render_template("network/attack_map.html", engagement=engagement, node_types=TARGET_NODE_TYPES)
