from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash
from datetime import datetime, timezone

from flask import flash, redirect, render_template, request, url_for
from flask_jwt_extended import create_access_token, set_access_cookies, unset_jwt_cookies

from app.auth_utils import csrf_protect
from app.blueprints.auth import bp
from app.extensions import db
from app.models.user import User

ph = PasswordHasher()


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        valid = False
        if user is not None and user.is_active:
            try:
                valid = ph.verify(user.password_hash, password)
            except (VerifyMismatchError, InvalidHash):
                valid = False

        if not valid:
            flash("Invalid username or password.", "danger")
            return render_template("auth/login.html", username=username)

        user.last_login_at = datetime.now(timezone.utc)
        db.session.commit()

        access_token = create_access_token(
            identity=str(user.id), additional_claims={"role": user.role}
        )
        response = redirect(url_for("engagements.list_engagements"))
        set_access_cookies(response, access_token)
        return response

    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST"])
@csrf_protect
def logout():
    response = redirect(url_for("auth.login"))
    unset_jwt_cookies(response)
    flash("Logged out.", "success")
    return response
