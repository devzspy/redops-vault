from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError
from flask import flash, redirect, render_template, request, url_for
from flask_jwt_extended import jwt_required

from app.auth_utils import csrf_protect, current_user
from app.blueprints.account import bp
from app.extensions import db

ph = PasswordHasher()


@bp.route("/password")
@jwt_required()
def change_password_form():
    user = current_user()
    return render_template("account/change_password.html", user=user)


@bp.route("/password", methods=["POST"])
@csrf_protect
def change_password():
    user = current_user()
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    try:
        current_valid = ph.verify(user.password_hash, current_password)
    except (VerifyMismatchError, InvalidHash):
        current_valid = False

    if not current_valid:
        flash("Current password is incorrect.", "danger")
        return render_template("account/change_password.html", user=user)
    if len(new_password) < 8:
        flash("New password must be at least 8 characters.", "danger")
        return render_template("account/change_password.html", user=user)
    if new_password != confirm_password:
        flash("New password and confirmation do not match.", "danger")
        return render_template("account/change_password.html", user=user)

    user.password_hash = ph.hash(new_password)
    user.must_change_password = False
    db.session.commit()
    flash("Password updated.", "success")
    return redirect(url_for("engagements.list_engagements"))
