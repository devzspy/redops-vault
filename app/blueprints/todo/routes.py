from datetime import datetime, timezone

from flask import abort, flash, redirect, request, url_for

from app.auth_utils import csrf_protect, current_user
from app.blueprints.todo import bp
from app.extensions import db
from app.models.engagement import Engagement
from app.models.todo import STATUS_DONE, STATUS_OPEN, Todo
from app.services import activity_service


@bp.route("/engagements/<int:engagement_id>/todos", methods=["POST"])
@csrf_protect
def create_todo(engagement_id):
    Engagement.query.get_or_404(engagement_id)

    title = request.form.get("title", "").strip()
    if not title:
        flash("Task title is required.", "danger")
        return redirect(url_for("engagements.engagement_detail", engagement_id=engagement_id))

    todo = Todo(
        engagement_id=engagement_id,
        title=title,
        notes=request.form.get("notes", "").strip() or None,
        created_by_id=int(current_user().id),
    )
    db.session.add(todo)
    db.session.flush()
    activity_service.log_activity(engagement_id, "todo", "created", f"Added task '{todo.title}'")
    db.session.commit()
    flash("Task added.", "success")
    return redirect(url_for("engagements.engagement_detail", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/todos/<int:todo_id>/claim", methods=["POST"])
@csrf_protect
def claim_todo(engagement_id, todo_id):
    todo = Todo.query.filter_by(id=todo_id, engagement_id=engagement_id).first_or_404()
    if todo.status == STATUS_DONE:
        abort(400, description="Cannot claim a completed task")

    actor = current_user()
    todo.assignee_id = actor.id
    todo.handoff_notes = None
    activity_service.log_activity(
        engagement_id, "todo", "claimed", f"Claimed task '{todo.title}'"
    )
    db.session.commit()
    flash("Task claimed.", "success")
    return redirect(url_for("engagements.engagement_detail", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/todos/<int:todo_id>/handoff", methods=["POST"])
@csrf_protect
def handoff_todo(engagement_id, todo_id):
    todo = Todo.query.filter_by(id=todo_id, engagement_id=engagement_id).first_or_404()
    if todo.status == STATUS_DONE:
        abort(400, description="Cannot hand off a completed task")

    previous_assignee = todo.assignee.username if todo.assignee else None
    todo.assignee_id = None
    todo.handoff_notes = request.form.get("handoff_notes", "").strip() or None

    summary = f"Handed off task '{todo.title}'"
    if previous_assignee:
        summary += f" (was: {previous_assignee})"
    activity_service.log_activity(engagement_id, "todo", "handed_off", summary)
    db.session.commit()
    flash("Task handed off.", "success")
    return redirect(url_for("engagements.engagement_detail", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/todos/<int:todo_id>/done", methods=["POST"])
@csrf_protect
def complete_todo(engagement_id, todo_id):
    todo = Todo.query.filter_by(id=todo_id, engagement_id=engagement_id).first_or_404()
    todo.status = STATUS_DONE
    todo.completed_at = datetime.now(timezone.utc)
    todo.completed_by_id = int(current_user().id)
    activity_service.log_activity(engagement_id, "todo", "completed", f"Completed task '{todo.title}'")
    db.session.commit()
    flash("Task marked done.", "success")
    return redirect(url_for("engagements.engagement_detail", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/todos/<int:todo_id>/reopen", methods=["POST"])
@csrf_protect
def reopen_todo(engagement_id, todo_id):
    todo = Todo.query.filter_by(id=todo_id, engagement_id=engagement_id).first_or_404()
    todo.status = STATUS_OPEN
    todo.completed_at = None
    todo.completed_by_id = None
    activity_service.log_activity(engagement_id, "todo", "reopened", f"Reopened task '{todo.title}'")
    db.session.commit()
    flash("Task reopened.", "success")
    return redirect(url_for("engagements.engagement_detail", engagement_id=engagement_id))


@bp.route("/engagements/<int:engagement_id>/todos/<int:todo_id>/delete", methods=["POST"])
@csrf_protect
def delete_todo(engagement_id, todo_id):
    todo = Todo.query.filter_by(id=todo_id, engagement_id=engagement_id).first_or_404()
    activity_service.log_activity(engagement_id, "todo", "deleted", f"Deleted task '{todo.title}'")
    db.session.delete(todo)
    db.session.commit()
    flash("Task deleted.", "success")
    return redirect(url_for("engagements.engagement_detail", engagement_id=engagement_id))
