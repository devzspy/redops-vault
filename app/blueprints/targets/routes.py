from flask import abort, flash, redirect, render_template, request, url_for
from flask_jwt_extended import jwt_required

from app.auth_utils import csrf_protect, current_user
from app.blueprints.targets import bp
from app.extensions import db
from app.models.engagement import Engagement
from app.models.infrastructure import (
    ROLE_TARGET,
    TARGET_NODE_TYPES,
    TARGET_ROLES,
    TARGET_STATUSES,
    InfrastructureEdge,
    InfrastructureNode,
)
from app.services import activity_service, target_detail_service


def _target_nodes(engagement_id):
    return (
        InfrastructureNode.query.filter_by(engagement_id=engagement_id)
        .filter(InfrastructureNode.role.in_(TARGET_ROLES))
        .order_by(InfrastructureNode.node_type.asc(), InfrastructureNode.name.asc())
        .all()
    )


def _target_edges(engagement_id):
    edges = InfrastructureEdge.query.filter_by(engagement_id=engagement_id).all()
    return [e for e in edges if e.source_node.role in TARGET_ROLES and e.target_node.role in TARGET_ROLES]


@bp.route("/engagements/<int:engagement_id>/targets")
@jwt_required()
def list_targets(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return render_template(
        "targets/list.html",
        engagement=engagement,
        nodes=_target_nodes(engagement_id),
        edges=_target_edges(engagement_id),
    )


@bp.route("/engagements/<int:engagement_id>/targets/<int:node_id>")
@jwt_required()
def target_detail(engagement_id, node_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    node = (
        InfrastructureNode.query.filter_by(id=node_id, engagement_id=engagement_id)
        .filter(InfrastructureNode.role.in_(TARGET_ROLES))
        .first_or_404()
    )
    edges = [e for e in _target_edges(engagement_id) if e.source_node_id == node.id or e.target_node_id == node.id]
    detail = target_detail_service.gather(node)
    return render_template("targets/detail.html", engagement=engagement, node=node, edges=edges, **detail)


@bp.route("/engagements/<int:engagement_id>/targets/new")
@jwt_required()
def new_target_form(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    default_role = request.args.get("role")
    if default_role not in TARGET_ROLES:
        default_role = ROLE_TARGET
    return render_template(
        "targets/node_form.html",
        engagement=engagement,
        node=None,
        node_types=TARGET_NODE_TYPES,
        roles=TARGET_ROLES,
        default_role=default_role,
        statuses=TARGET_STATUSES,
    )


@bp.route("/engagements/<int:engagement_id>/targets", methods=["POST"])
@csrf_protect
def create_target(engagement_id):
    Engagement.query.get_or_404(engagement_id)

    node_type = request.form.get("node_type")
    name = request.form.get("name", "").strip()
    if node_type not in TARGET_NODE_TYPES or not name:
        flash("Type and name are required.", "danger")
        return redirect(url_for("targets.new_target_form", engagement_id=engagement_id))

    role = request.form.get("role")
    if role not in TARGET_ROLES:
        abort(400, description="Invalid role")

    status = request.form.get("status") or None
    if status and status not in TARGET_STATUSES:
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
        engagement_id, "infrastructure_node", "created", f"Added target/victim '{node.name}'"
    )
    db.session.commit()
    flash("Target / victim added.", "success")
    return redirect(url_for("targets.list_targets", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/targets/<int:node_id>/edit")
@jwt_required()
def edit_target_form(engagement_id, node_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    node = InfrastructureNode.query.filter_by(
        id=node_id, engagement_id=engagement_id
    ).filter(InfrastructureNode.role.in_(TARGET_ROLES)).first_or_404()
    return render_template(
        "targets/node_form.html",
        engagement=engagement,
        node=node,
        node_types=TARGET_NODE_TYPES,
        roles=TARGET_ROLES,
        default_role=None,
        statuses=TARGET_STATUSES,
    )


@bp.route("/engagements/<int:engagement_id>/targets/<int:node_id>/edit", methods=["POST"])
@csrf_protect
def edit_target(engagement_id, node_id):
    node = InfrastructureNode.query.filter_by(
        id=node_id, engagement_id=engagement_id
    ).filter(InfrastructureNode.role.in_(TARGET_ROLES)).first_or_404()

    node_type = request.form.get("node_type")
    name = request.form.get("name", "").strip()
    if node_type not in TARGET_NODE_TYPES or not name:
        flash("Type and name are required.", "danger")
        return redirect(url_for("targets.edit_target_form", engagement_id=engagement_id, node_id=node_id))

    role = request.form.get("role")
    if role not in TARGET_ROLES:
        abort(400, description="Invalid role")

    status = request.form.get("status") or None
    if status and status not in TARGET_STATUSES:
        abort(400, description="Invalid status")

    node.node_type = node_type
    node.name = name
    node.role = role
    node.status = status
    node.provider = request.form.get("provider", "").strip() or None
    node.region = request.form.get("region", "").strip() or None
    node.notes = request.form.get("notes", "").strip() or None
    activity_service.log_activity(
        engagement_id, "infrastructure_node", "updated", f"Updated target/victim '{node.name}'"
    )
    db.session.commit()
    flash("Target / victim updated.", "success")
    return redirect(url_for("targets.list_targets", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/targets/<int:node_id>/delete", methods=["POST"])
@csrf_protect
def delete_target(engagement_id, node_id):
    node = InfrastructureNode.query.filter_by(
        id=node_id, engagement_id=engagement_id
    ).filter(InfrastructureNode.role.in_(TARGET_ROLES)).first_or_404()
    activity_service.log_activity(
        engagement_id, "infrastructure_node", "deleted", f"Deleted target/victim '{node.name}'"
    )
    db.session.delete(node)
    db.session.commit()
    flash("Target / victim deleted.", "success")
    return redirect(url_for("targets.list_targets", engagement_id=engagement_id))


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
    if source.role not in TARGET_ROLES or target.role not in TARGET_ROLES:
        abort(400, description="Source and target must both be targets/victims")

    return source_id, target_id, None


@bp.route("/engagements/<int:engagement_id>/targets/edges/new")
@jwt_required()
def new_edge_form(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    return render_template(
        "targets/edge_form.html", engagement=engagement, nodes=_target_nodes(engagement_id), edge=None
    )


@bp.route("/engagements/<int:engagement_id>/targets/edges", methods=["POST"])
@csrf_protect
def create_edge(engagement_id):
    Engagement.query.get_or_404(engagement_id)

    source_id, target_id, error_response = _resolve_edge_nodes(engagement_id, "targets.new_edge_form")
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
    return redirect(url_for("targets.list_targets", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/targets/edges/<int:edge_id>/edit")
@jwt_required()
def edit_edge_form(engagement_id, edge_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    edge = InfrastructureEdge.query.filter_by(id=edge_id, engagement_id=engagement_id).first_or_404()
    if edge.source_node.role not in TARGET_ROLES or edge.target_node.role not in TARGET_ROLES:
        return redirect(url_for("infrastructure.edit_edge_form", engagement_id=engagement_id, edge_id=edge_id))
    return render_template(
        "targets/edge_form.html", engagement=engagement, nodes=_target_nodes(engagement_id), edge=edge
    )


@bp.route("/engagements/<int:engagement_id>/targets/edges/<int:edge_id>/edit", methods=["POST"])
@csrf_protect
def edit_edge(engagement_id, edge_id):
    edge = InfrastructureEdge.query.filter_by(id=edge_id, engagement_id=engagement_id).first_or_404()
    if edge.source_node.role not in TARGET_ROLES or edge.target_node.role not in TARGET_ROLES:
        abort(404)

    source_id, target_id, error_response = _resolve_edge_nodes(
        engagement_id, "targets.edit_edge_form", edge_id=edge_id
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
    return redirect(url_for("targets.list_targets", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/targets/edges/<int:edge_id>/delete", methods=["POST"])
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
    return redirect(url_for("targets.list_targets", engagement_id=engagement_id))
