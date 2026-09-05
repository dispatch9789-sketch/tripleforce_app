"""Triple Force Logistic LLC — Flask application factory."""
import os
import logging
from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix
from app.config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ── Production reverse-proxy support ──
    if not app.config.get("DEBUG"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # ── Ensure upload folder exists ──
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # ── Initialize extensions ──
    from app.extensions import db, login_manager, csrf, mail, migrate

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    # ── Logging ──
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # ── Register blueprints ──
    from app.auth.routes import auth
    from app.main.routes import main
    from app.customers.routes import customers
    from app.quotes.routes import quotes
    from app.dispatch.routes import dispatch
    from app.invoices.routes import invoices
    from app.reports.routes import reports
    from app.reminders.routes import reminders
    from app.users.routes import users
    from app.driver_portal.routes import driver_portal
    from app.driver_ops.routes import driver_ops
    from app.outreach.routes import outreach, register_cli as register_outreach_cli
    from app.public_request.routes import public

    app.register_blueprint(auth, url_prefix="/auth")
    app.register_blueprint(main)
    app.register_blueprint(customers, url_prefix="/customers")
    app.register_blueprint(quotes, url_prefix="/quotes")
    app.register_blueprint(dispatch, url_prefix="/dispatch")
    app.register_blueprint(invoices, url_prefix="/invoices")
    app.register_blueprint(reports, url_prefix="/reports")
    app.register_blueprint(reminders, url_prefix="/reminders")
    app.register_blueprint(users, url_prefix="/users")
    app.register_blueprint(driver_portal, url_prefix="/driver")
    app.register_blueprint(driver_ops, url_prefix="/driver-ops")
    app.register_blueprint(outreach, url_prefix="/outreach")
    app.register_blueprint(public)  # public customer-facing pages (/request-pickup)

    # ── Outreach Tracker CLI (flask outreach-import <path>) ──
    register_outreach_cli(app)

    # ── Jinja context processors ──
    from app.utils import inject_settings, format_currency, format_datetime

    app.context_processor(inject_settings)
    app.jinja_env.filters["currency"] = format_currency
    app.jinja_env.filters["datetime"] = format_datetime

    # ── User loader ──
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # ── Create tables on first run ──
    with app.app_context():
        db.create_all()

    # ── Ensure new public pickup-request columns exist on existing DBs ──
    # Railway deploys with gunicorn only (no `flask db upgrade`), and
    # db.create_all() does not add columns to existing tables. This
    # idempotent ALTER TABLE pass makes new customer-form fields persist on
    # already-deployed databases without losing existing data.
    from app.schema_migrations import ensure_delivery_columns, ensure_pricing_columns, seed_checklist_items
    ensure_delivery_columns(app, db)
    ensure_pricing_columns(app, db)
    seed_checklist_items(app, db)

    # ── No-cache headers for authenticated staff pages ──
    # Prevents the browser Back button from revealing usable staff pages
    # after logout. Applied only when a user is authenticated (and never to
    # static assets or the intentionally-public customer pages), so public
    # pages and static files remain cacheable.
    from flask_login import current_user

    @app.after_request
    def _add_security_headers(response):
        endpoint = request.endpoint or ""
        # Never interfere with static asset delivery.
        if endpoint == "static" or endpoint.startswith("static."):
            return response
        # Only set no-store on authenticated (staff) responses. Public pages
        # (/ and /request-pickup) stay cacheable for customers.
        if current_user.is_authenticated:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    # ── Error handlers ──
    from app.main.routes import page_not_found, internal_error, forbidden
    from flask_wtf.csrf import CSRFError

    app.register_error_handler(404, page_not_found)
    app.register_error_handler(500, internal_error)
    app.register_error_handler(403, forbidden)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        from flask import render_template
        return render_template("errors/400.html", reason=e.description), 400

    return app
