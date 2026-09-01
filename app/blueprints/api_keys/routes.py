from datetime import datetime, timezone

from flask import abort, flash, redirect, render_template, request, url_for
from flask_jwt_extended import jwt_required

from app.auth_utils import csrf_protect, current_user
from app.blueprints.api_keys import bp
from app.extensions import db
from app.models.api_key import ApiKey
from app.services import api_key_service


@bp.route("")
@jwt_required()
def list_keys():
    user = current_user()
    keys = ApiKey.query.filter_by(user_id=user.id).order_by(ApiKey.created_at.desc()).all()
    return render_template("api_keys/list.html", keys=keys)


@bp.route("", methods=["POST"])
@csrf_protect
def create_key():
    user = current_user()
    name = request.form.get("name", "").strip()
    if not name:
        flash("A name is required to identify the key.", "danger")
        return redirect(url_for("api_keys.list_keys"))

    token, key_hash, key_prefix = api_key_service.generate_key()
    key = ApiKey(user_id=user.id, name=name, key_hash=key_hash, key_prefix=key_prefix)
    db.session.add(key)
    db.session.commit()
    flash(f"API key created. Copy it now, it won't be shown again: {token}", "success")
    return redirect(url_for("api_keys.list_keys"))


@bp.route("/<int:key_id>/revoke", methods=["POST"])
@csrf_protect
def revoke_key(key_id):
    user = current_user()
    key = ApiKey.query.filter_by(id=key_id, user_id=user.id).first()
    if key is None:
        abort(404)

    if key.is_active():
        key.revoked_at = datetime.now(timezone.utc)
        db.session.commit()
        flash(f"API key '{key.name}' revoked.", "success")
    return redirect(url_for("api_keys.list_keys"))
