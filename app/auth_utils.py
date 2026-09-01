import hashlib
from datetime import datetime, timezone
from functools import wraps

from flask import abort, current_app, g, jsonify, redirect, request, url_for
from flask_jwt_extended import get_jwt, jwt_required, verify_jwt_in_request

from app.models.user import ROLE_BLUETEAM, User


def register_setup_gate(app):
    @app.before_request
    def _redirect_to_setup_if_no_users():
        if request.path.startswith("/static/") or request.path == "/setup":
            return None

        if not app.config.get("SETUP_COMPLETE"):
            if User.query.count() == 0:
                return redirect(url_for("setup.wizard"))
            app.config["SETUP_COMPLETE"] = True

        return None


def register_password_change_gate(app):
    """Forces a user whose password was reset by an admin (User.must_change_password)
    to set a new password before reaching anywhere else in the app.
    """

    @app.before_request
    def _redirect_to_password_change_if_required():
        if request.path.startswith("/static/") or request.path.startswith("/api/v1/"):
            return None

        if request.blueprint in ("auth", "account", "setup"):
            return None

        try:
            verify_jwt_in_request(optional=True)
        except Exception:
            return None

        user = current_user()
        if user is not None and user.needs_password_change():
            return redirect(url_for("account.change_password_form"))

        return None


def register_blueteam_gate(app):
    """BlueTeam users are strictly read-only, and only within engagements
    they've been explicitly assigned to. Every engagement-scoped blueprint
    consistently uses <int:engagement_id> in its URL, so this single hook
    covers all of them instead of decorating each route individually.
    """

    @app.before_request
    def _restrict_blueteam():
        if request.path.startswith("/static/"):
            return None

        try:
            verify_jwt_in_request(optional=True)
        except Exception:
            return None

        claims = get_jwt()
        if not claims or claims.get("role") != ROLE_BLUETEAM:
            return None

        if request.blueprint == "auth":
            return None

        if request.blueprint in ("admin", "backups"):
            abort(403)

        if request.method not in ("GET", "HEAD", "OPTIONS"):
            abort(403)

        engagement_id = (request.view_args or {}).get("engagement_id")
        if engagement_id is not None:
            from app.models.engagement_assignment import EngagementAssignment

            user = current_user()
            assigned = (
                user is not None
                and EngagementAssignment.query.filter_by(
                    engagement_id=engagement_id, user_id=user.id
                ).first()
                is not None
            )
            if not assigned:
                abort(403)

        return None


def register_api_key_gate(app):
    """Authenticates every request under /api/v1/ against an `Authorization:
    Bearer <token>` API key instead of the cookie-based JWT the rest of the
    app uses. Mirrors register_blueteam_gate's read-only/engagement-scoped
    restriction for blueteam-role keys, since that gate never fires here
    (it only recognizes a JWT identity, and API requests carry none).
    """

    @app.before_request
    def _authenticate_api_key():
        if not request.path.startswith("/api/v1/"):
            return None

        from app.models.api_key import ApiKey
        from app.models.engagement_assignment import EngagementAssignment

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify(error="missing_api_key", message="Authorization: Bearer <token> header is required"), 401

        token = auth_header[len("Bearer "):].strip()
        if not token:
            return jsonify(error="missing_api_key", message="Authorization: Bearer <token> header is required"), 401

        key_hash = hashlib.sha256(token.encode()).hexdigest()
        api_key = ApiKey.query.filter_by(key_hash=key_hash).first()
        if api_key is None or not api_key.is_active():
            return jsonify(error="invalid_api_key", message="Unknown or revoked API key"), 401

        user = api_key.user
        if user is None or not user.is_active:
            return jsonify(error="invalid_api_key", message="Unknown or revoked API key"), 401

        from app.extensions import db

        api_key.last_used_at = datetime.now(timezone.utc)
        db.session.commit()

        g.api_key = api_key
        g.api_user = user

        if user.role == ROLE_BLUETEAM:
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                return jsonify(error="forbidden", message="This API key is read-only"), 403

            engagement_id = (request.view_args or {}).get("engagement_id")
            if engagement_id is not None:
                assigned = EngagementAssignment.query.filter_by(
                    engagement_id=engagement_id, user_id=user.id
                ).first()
                if assigned is None:
                    return jsonify(error="forbidden", message="Not assigned to this engagement"), 403

        return None


def current_api_user():
    """Load the User row authenticated for the current /api/v1 request via
    register_api_key_gate, if any.
    """
    return getattr(g, "api_user", None)


def csrf_protect(view_func):
    """For state-changing routes: verifies the JWT and confirms the
    hidden csrf_token form field matches the CSRF claim embedded in the JWT
    by Flask-JWT-Extended. Native HTML forms cannot set custom headers, so
    this checks a form field instead of the X-CSRF-TOKEN header.
    """

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        expected = get_jwt().get("csrf")
        supplied = request.form.get("csrf_token")
        if not expected or not supplied or supplied != expected:
            abort(400, description="Missing or invalid CSRF token")
        return view_func(*args, **kwargs)

    return wrapper


def role_required(role):
    def decorator(view_func):
        @wraps(view_func)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            if claims.get("role") != role:
                abort(403)
            return view_func(*args, **kwargs)

        return wrapper

    return decorator


def role_required_csrf(role):
    """Combines role_required and csrf_protect for state-changing admin routes:
    verifies the JWT, checks the CSRF form field, and enforces the given role.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            expected = claims.get("csrf")
            supplied = request.form.get("csrf_token")
            if not expected or not supplied or supplied != expected:
                abort(400, description="Missing or invalid CSRF token")
            if claims.get("role") != role:
                abort(403)
            return view_func(*args, **kwargs)

        return wrapper

    return decorator


def current_user():
    """Load the User row for the currently authenticated request, whether
    that's a cookie-based JWT session (the HTML routes) or an /api/v1
    Bearer API key (register_api_key_gate). Falling back to the API-key
    identity here -- rather than only in the API blueprints themselves --
    means shared code like activity_service.log_activity() attributes
    actions to the right user regardless of which auth path made the call.
    """
    from flask_jwt_extended import get_jwt_identity

    identity = get_jwt_identity()
    if identity is not None:
        return User.query.get(int(identity))
    return current_api_user()
