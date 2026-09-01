import secrets

from argon2 import PasswordHasher
from flask import flash, redirect, render_template, request, url_for

from app.auth_utils import current_user, role_required, role_required_csrf
from app.blueprints.admin import bp
from app.extensions import db
from app.models.engagement import Engagement
from app.models.engagement_assignment import EngagementAssignment
from app.models.user import ROLE_ADMIN, ROLE_BLUETEAM, ROLE_OPERATOR, ROLES, User

ph = PasswordHasher()


def _other_active_admins_exist(excluding_user_id):
    return (
        User.query.filter(User.role == ROLE_ADMIN, User.is_active.is_(True), User.id != excluding_user_id)
        .count()
        > 0
    )


@bp.route("/users")
@role_required("admin")
def list_users():
    users = User.query.order_by(User.username.asc()).all()
    return render_template("admin/users_list.html", users=users)


@bp.route("/users/new")
@role_required("admin")
def new_user_form():
    return render_template("admin/user_form.html", user=None, roles=ROLES)


@bp.route("/users", methods=["POST"])
@role_required_csrf("admin")
def create_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", ROLE_OPERATOR)

    if role not in ROLES:
        role = ROLE_OPERATOR

    if not username or len(username) < 3:
        flash("Username must be at least 3 characters.", "danger")
        return redirect(url_for("admin.new_user_form"))
    if not password or len(password) < 8:
        flash("Password must be at least 8 characters.", "danger")
        return redirect(url_for("admin.new_user_form"))
    if User.query.filter_by(username=username).first() is not None:
        flash("A user with that username already exists.", "danger")
        return redirect(url_for("admin.new_user_form"))

    user = User(username=username, password_hash=ph.hash(password), role=role)
    db.session.add(user)
    db.session.commit()
    flash(f"User '{username}' created.", "success")
    return redirect(url_for("admin.list_users"))


@bp.route("/users/<int:user_id>/edit")
@role_required("admin")
def edit_user_form(user_id):
    user = User.query.get_or_404(user_id)
    all_engagements = Engagement.query.order_by(Engagement.name.asc()).all()
    assigned_engagement_ids = {a.engagement_id for a in user.engagement_assignments}
    return render_template(
        "admin/user_form.html",
        user=user,
        roles=ROLES,
        all_engagements=all_engagements,
        assigned_engagement_ids=assigned_engagement_ids,
    )


@bp.route("/users/<int:user_id>/edit", methods=["POST"])
@role_required_csrf("admin")
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    role = request.form.get("role", user.role)
    is_active = request.form.get("is_active") == "on"

    if role not in ROLES:
        role = user.role

    acting_user = current_user()
    demoting_last_admin = (
        user.role == ROLE_ADMIN
        and (role != ROLE_ADMIN or not is_active)
        and not _other_active_admins_exist(user.id)
    )
    if demoting_last_admin:
        flash("Cannot demote or deactivate the last remaining admin.", "danger")
        return redirect(url_for("admin.edit_user_form", user_id=user_id))

    user.role = role
    user.is_active = is_active

    if role == ROLE_BLUETEAM:
        requested_ids = {int(v) for v in request.form.getlist("engagement_ids") if v.isdigit()}
        current_ids = {a.engagement_id for a in user.engagement_assignments}
        for engagement_id in requested_ids - current_ids:
            db.session.add(
                EngagementAssignment(
                    engagement_id=engagement_id, user_id=user.id, assigned_by_id=acting_user.id
                )
            )
        for assignment in user.engagement_assignments:
            if assignment.engagement_id not in requested_ids:
                db.session.delete(assignment)

    db.session.commit()

    if user.id == acting_user.id and role != ROLE_ADMIN:
        flash("Your account has been changed to operator; admin routes are no longer available.", "warning")
    else:
        flash(f"User '{user.username}' updated.", "success")
    return redirect(url_for("admin.list_users"))


@bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@role_required_csrf("admin")
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get("password", "").strip()
    if not new_password:
        new_password = secrets.token_urlsafe(12)
        flash(f"Generated temporary password for '{user.username}': {new_password}", "info")
    elif len(new_password) < 8:
        flash("Password must be at least 8 characters.", "danger")
        return redirect(url_for("admin.edit_user_form", user_id=user_id))
    else:
        flash(f"Password reset for '{user.username}'.", "success")

    user.password_hash = ph.hash(new_password)
    user.must_change_password = True
    db.session.commit()
    return redirect(url_for("admin.edit_user_form", user_id=user_id))


@bp.route("/users/<int:user_id>/deactivate", methods=["POST"])
@role_required_csrf("admin")
def deactivate_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.role == ROLE_ADMIN and not _other_active_admins_exist(user.id):
        flash("Cannot deactivate the last remaining admin.", "danger")
        return redirect(url_for("admin.list_users"))

    user.is_active = False
    db.session.commit()
    flash(f"User '{user.username}' deactivated.", "success")
    return redirect(url_for("admin.list_users"))
