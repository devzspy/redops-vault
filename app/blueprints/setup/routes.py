from argon2 import PasswordHasher
from flask import current_app, flash, redirect, render_template, request, url_for

from app.blueprints.setup import bp
from app.extensions import db
from app.models.app_setting import INFRA_ENGAGEMENT, INFRA_MODES, INFRA_STANDING, AppSetting
from app.models.engagement import STATUS_ACTIVE, Engagement
from app.models.killchain import KILL_CHAIN_MODEL_LABELS, KILL_CHAIN_MODEL_LMCKC, KILL_CHAIN_MODELS
from app.models.user import ROLE_ADMIN, User

ph = PasswordHasher()


@bp.route("", methods=["GET", "POST"])
def wizard():
    # Defense in depth: independently re-check even though the app-level
    # before_request gate should already keep this unreachable post-setup.
    if User.query.count() > 0:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        infra_mode = request.form.get("infra_mode", "")
        engagement_name = request.form.get("engagement_name", "").strip()
        default_kill_chain_model = request.form.get("default_kill_chain_model") or KILL_CHAIN_MODEL_LMCKC

        error = None
        if not username or len(username) < 3:
            error = "Username must be at least 3 characters."
        elif not password or len(password) < 8:
            error = "Password must be at least 8 characters."
        elif password != confirm:
            error = "Passwords do not match."
        elif infra_mode not in INFRA_MODES:
            error = "Please select how this vault will be run."
        elif infra_mode == INFRA_ENGAGEMENT and not engagement_name:
            error = "Engagement name is required for engagement infrastructure."
        elif default_kill_chain_model not in KILL_CHAIN_MODELS:
            error = "Please select a kill chain model."

        if error:
            flash(error, "danger")
            return render_template(
                "setup/wizard.html",
                username=username,
                infra_mode=infra_mode,
                engagement_name=engagement_name,
                default_kill_chain_model=default_kill_chain_model,
                kill_chain_models=KILL_CHAIN_MODELS,
                kill_chain_model_labels=KILL_CHAIN_MODEL_LABELS,
            )

        user = User(username=username, password_hash=ph.hash(password), role=ROLE_ADMIN)
        db.session.add(user)
        db.session.flush()

        setting = AppSetting(id=1, infra_mode=infra_mode, default_kill_chain_model=default_kill_chain_model)
        if infra_mode == INFRA_ENGAGEMENT:
            engagement = Engagement(
                name=engagement_name,
                client_name=engagement_name,
                status=STATUS_ACTIVE,
                kill_chain_model=default_kill_chain_model,
                created_by_id=user.id,
            )
            db.session.add(engagement)
            db.session.flush()
            setting.engagement_id = engagement.id
        db.session.add(setting)

        db.session.commit()

        current_app.config["SETUP_COMPLETE"] = True

        flash("Admin account created. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template(
        "setup/wizard.html",
        infra_mode=INFRA_STANDING,
        default_kill_chain_model=KILL_CHAIN_MODEL_LMCKC,
        kill_chain_models=KILL_CHAIN_MODELS,
        kill_chain_model_labels=KILL_CHAIN_MODEL_LABELS,
    )
