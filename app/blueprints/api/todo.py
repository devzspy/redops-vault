from datetime import datetime, timezone

from flask import Blueprint, abort, jsonify

from app.auth_utils import current_api_user
from app.blueprints.api import serializers
from app.blueprints.api._common import json_body, require_fields, str_or_none
from app.extensions import db
from app.models.engagement import Engagement
from app.models.todo import STATUS_DONE, STATUS_OPEN, Todo
from app.services import activity_service

bp = Blueprint("api_todo", __name__, url_prefix="/api/v1/engagements/<int:engagement_id>/todos")


@bp.route("", methods=["GET"])
def list_todos(engagement_id):
    engagement = Engagement.query.get_or_404(engagement_id)
    todos = Todo.query.filter_by(engagement_id=engagement_id).order_by(Todo.created_at.asc()).all()
    return jsonify(todos=[serializers.todo_dict(t) for t in todos])


@bp.route("", methods=["POST"])
def create_todo(engagement_id):
    Engagement.query.get_or_404(engagement_id)
    data = json_body()
    require_fields(data, "title")

    todo = Todo(
        engagement_id=engagement_id,
        title=data["title"].strip(),
        notes=str_or_none(data.get("notes")),
        created_by_id=current_api_user().id,
    )
    db.session.add(todo)
    db.session.flush()
    activity_service.log_activity(engagement_id, "todo", "created", f"Added task '{todo.title}'")
    db.session.commit()
    return jsonify(serializers.todo_dict(todo)), 201


@bp.route("/<int:todo_id>", methods=["GET"])
def get_todo(engagement_id, todo_id):
    todo = Todo.query.filter_by(id=todo_id, engagement_id=engagement_id).first_or_404()
    return jsonify(serializers.todo_dict(todo))


@bp.route("/<int:todo_id>/claim", methods=["POST"])
def claim_todo(engagement_id, todo_id):
    todo = Todo.query.filter_by(id=todo_id, engagement_id=engagement_id).first_or_404()
    if todo.status == STATUS_DONE:
        abort(400, description="Cannot claim a completed task")

    todo.assignee_id = current_api_user().id
    todo.handoff_notes = None
    activity_service.log_activity(engagement_id, "todo", "claimed", f"Claimed task '{todo.title}'")
    db.session.commit()
    return jsonify(serializers.todo_dict(todo))


@bp.route("/<int:todo_id>/handoff", methods=["POST"])
def handoff_todo(engagement_id, todo_id):
    todo = Todo.query.filter_by(id=todo_id, engagement_id=engagement_id).first_or_404()
    if todo.status == STATUS_DONE:
        abort(400, description="Cannot hand off a completed task")

    previous_assignee = todo.assignee.username if todo.assignee else None
    todo.assignee_id = None
    todo.handoff_notes = str_or_none(json_body().get("handoff_notes"))

    summary = f"Handed off task '{todo.title}'"
    if previous_assignee:
        summary += f" (was: {previous_assignee})"
    activity_service.log_activity(engagement_id, "todo", "handed_off", summary)
    db.session.commit()
    return jsonify(serializers.todo_dict(todo))


@bp.route("/<int:todo_id>/done", methods=["POST"])
def complete_todo(engagement_id, todo_id):
    todo = Todo.query.filter_by(id=todo_id, engagement_id=engagement_id).first_or_404()
    todo.status = STATUS_DONE
    todo.completed_at = datetime.now(timezone.utc)
    todo.completed_by_id = current_api_user().id
    activity_service.log_activity(engagement_id, "todo", "completed", f"Completed task '{todo.title}'")
    db.session.commit()
    return jsonify(serializers.todo_dict(todo))


@bp.route("/<int:todo_id>/reopen", methods=["POST"])
def reopen_todo(engagement_id, todo_id):
    todo = Todo.query.filter_by(id=todo_id, engagement_id=engagement_id).first_or_404()
    todo.status = STATUS_OPEN
    todo.completed_at = None
    todo.completed_by_id = None
    activity_service.log_activity(engagement_id, "todo", "reopened", f"Reopened task '{todo.title}'")
    db.session.commit()
    return jsonify(serializers.todo_dict(todo))


@bp.route("/<int:todo_id>", methods=["DELETE"])
def delete_todo(engagement_id, todo_id):
    todo = Todo.query.filter_by(id=todo_id, engagement_id=engagement_id).first_or_404()
    activity_service.log_activity(engagement_id, "todo", "deleted", f"Deleted task '{todo.title}'")
    db.session.delete(todo)
    db.session.commit()
    return "", 204
