import os
import sqlite3

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import get_jwt, verify_jwt_in_request
from flask_migrate import upgrade as migrate_upgrade
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.auth_utils import (
    current_user,
    register_api_key_gate,
    register_blueteam_gate,
    register_password_change_gate,
    register_setup_gate,
)
from app.extensions import db, jwt, migrate

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "migrations")


def create_app(config_object="config.Config"):
    load_dotenv()

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)

    os.makedirs(app.config["INSTANCE_DIR"], exist_ok=True)

    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db, directory=MIGRATIONS_DIR)

    @event.listens_for(Engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        if not isinstance(dbapi_connection, sqlite3.Connection):
            return
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    from app import models  # noqa: F401  (registers models with SQLAlchemy metadata)

    with app.app_context():
        migrate_upgrade(directory=MIGRATIONS_DIR)

    register_setup_gate(app)
    register_password_change_gate(app)
    register_blueteam_gate(app)
    register_api_key_gate(app)
    _register_blueprints(app)
    _register_context_processors(app)
    _register_template_filters(app)
    _register_error_handlers(app)
    _register_jwt_callbacks(app)

    from app.services import scheduler_service

    scheduler_service.init_scheduler(app)

    return app


def _register_blueprints(app):
    from app.blueprints.account import bp as account_bp
    from app.blueprints.admin import bp as admin_bp
    from app.blueprints.api_keys import bp as api_keys_bp
    from app.blueprints.attack import bp as attack_bp
    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.backups import bp as backups_bp
    from app.blueprints.engagements import bp as engagements_bp
    from app.blueprints.findings import bp as findings_bp
    from app.blueprints.help import bp as help_bp
    from app.blueprints.infrastructure import bp as infrastructure_bp
    from app.blueprints.ioc import bp as ioc_bp
    from app.blueprints.killchain import bp as killchain_bp
    from app.blueprints.loot import bp as loot_bp
    from app.blueprints.scaffolding import bp as scaffolding_bp
    from app.blueprints.setup import bp as setup_bp
    from app.blueprints.targets import bp as targets_bp
    from app.blueprints.threat_model import bp as threat_model_bp
    from app.blueprints.todo import bp as todo_bp

    app.register_blueprint(setup_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(engagements_bp)
    app.register_blueprint(loot_bp)
    app.register_blueprint(attack_bp)
    app.register_blueprint(killchain_bp)
    app.register_blueprint(infrastructure_bp)
    app.register_blueprint(targets_bp)
    app.register_blueprint(findings_bp)
    app.register_blueprint(ioc_bp)
    app.register_blueprint(threat_model_bp)
    app.register_blueprint(todo_bp)
    app.register_blueprint(scaffolding_bp)
    app.register_blueprint(backups_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_keys_bp)
    app.register_blueprint(help_bp)
    app.register_blueprint(account_bp)

    from app.blueprints.api.activity import bp as api_activity_bp
    from app.blueprints.api.attack import bp as api_attack_bp
    from app.blueprints.api.credentials import bp as api_credentials_bp
    from app.blueprints.api.engagements import bp as api_engagements_bp
    from app.blueprints.api.findings import bp as api_findings_bp
    from app.blueprints.api.infrastructure import bp as api_infrastructure_bp
    from app.blueprints.api.ioc import bp as api_ioc_bp
    from app.blueprints.api.killchain import bp as api_killchain_bp
    from app.blueprints.api.loot import bp as api_loot_bp
    from app.blueprints.api.targets import bp as api_targets_bp
    from app.blueprints.api.threat_model import bp as api_threat_model_bp
    from app.blueprints.api.todo import bp as api_todo_bp

    app.register_blueprint(api_engagements_bp)
    app.register_blueprint(api_findings_bp)
    app.register_blueprint(api_loot_bp)
    app.register_blueprint(api_credentials_bp)
    app.register_blueprint(api_killchain_bp)
    app.register_blueprint(api_infrastructure_bp)
    app.register_blueprint(api_targets_bp)
    app.register_blueprint(api_ioc_bp)
    app.register_blueprint(api_threat_model_bp)
    app.register_blueprint(api_todo_bp)
    app.register_blueprint(api_attack_bp)
    app.register_blueprint(api_activity_bp)

    @app.route("/")
    def index():
        from app.models.user import User

        if User.query.count() == 0:
            return redirect(url_for("setup.wizard"))
        try:
            verify_jwt_in_request(optional=True)
        except Exception:
            return redirect(url_for("auth.login"))
        from flask_jwt_extended import get_jwt_identity

        if get_jwt_identity() is None:
            return redirect(url_for("auth.login"))
        return redirect(url_for("engagements.list_engagements"))


def _register_context_processors(app):
    @app.context_processor
    def inject_globals():
        csrf_token_value = None
        user = None
        try:
            verify_jwt_in_request(optional=True)
            claims = get_jwt()
            csrf_token_value = claims.get("csrf") if claims else None
            user = current_user()
        except Exception:
            pass
        return {"csrf_token_value": csrf_token_value, "logged_in_user": user}


def _register_template_filters(app):
    from app.models.backup import (
        FREQUENCY_LABELS,
        PROVIDER_LABELS,
        RUN_STATUS_LABELS,
        SCOPE_LABELS,
        STORAGE_TYPE_LABELS,
    )
    from app.models.infrastructure import NODE_TYPE_LABELS
    from app.models.loot import CREDENTIAL_STATUS_LABELS, CREDENTIAL_TYPE_LABELS

    @app.template_filter("node_type_label")
    def node_type_label(value):
        return NODE_TYPE_LABELS.get(value, value)

    @app.template_filter("credential_type_label")
    def credential_type_label(value):
        return CREDENTIAL_TYPE_LABELS.get(value, value)

    @app.template_filter("credential_status_label")
    def credential_status_label(value):
        return CREDENTIAL_STATUS_LABELS.get(value, value)

    @app.template_filter("backup_provider_label")
    def backup_provider_label(value):
        return PROVIDER_LABELS.get(value, value)

    @app.template_filter("backup_storage_type_label")
    def backup_storage_type_label(value):
        return STORAGE_TYPE_LABELS.get(value, value)

    @app.template_filter("backup_scope_label")
    def backup_scope_label(value):
        return SCOPE_LABELS.get(value, value)

    @app.template_filter("backup_frequency_label")
    def backup_frequency_label(value):
        return FREQUENCY_LABELS.get(value, value)

    @app.template_filter("backup_run_status_label")
    def backup_run_status_label(value):
        return RUN_STATUS_LABELS.get(value, value)


def _register_error_handlers(app):
    def _is_api_request():
        return request.path.startswith("/api/v1/")

    @app.errorhandler(400)
    def bad_request(e):
        if _is_api_request():
            return jsonify(error="bad_request", message=e.description or "Bad request"), 400
        return e

    @app.errorhandler(403)
    def forbidden(e):
        if _is_api_request():
            return jsonify(error="forbidden", message=e.description or "Forbidden"), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        if _is_api_request():
            return jsonify(error="not_found", message=e.description or "Not found"), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        if _is_api_request():
            return jsonify(error="server_error", message="Internal server error"), 500
        return render_template("errors/500.html"), 500


def _register_jwt_callbacks(app):
    @jwt.unauthorized_loader
    def _unauthorized(reason):
        flash("Please log in to continue.", "warning")
        return redirect(url_for("auth.login"))

    @jwt.invalid_token_loader
    def _invalid_token(reason):
        flash("Your session is invalid, please log in again.", "warning")
        return redirect(url_for("auth.login"))

    @jwt.expired_token_loader
    def _expired_token(header, payload):
        flash("Your session has expired, please log in again.", "warning")
        return redirect(url_for("auth.login"))

    @jwt.token_in_blocklist_loader
    def _check_revoked(jwt_header, jwt_payload):
        from app.models.user import User

        user = User.query.get(int(jwt_payload["sub"]))
        if user is None or not user.is_active:
            return True
        return user.role != jwt_payload.get("role")

    @jwt.revoked_token_loader
    def _revoked_token(header, payload):
        flash("Your session is no longer valid, please log in again.", "warning")
        return redirect(url_for("auth.login"))
