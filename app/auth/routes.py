"""Authentication blueprint: login, logout, password reset."""
from datetime import datetime, timedelta
import secrets

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse, urljoin

from app.extensions import db
from app.models import User
from app.forms import LoginForm, PasswordResetRequestForm, PasswordResetForm, ChangePasswordForm
from app.utils import send_email, get_company_settings

auth = Blueprint("auth", __name__)


def _default_landing_page(user):
    """Return the appropriate landing route for a user's role."""
    if user.role == "driver":
        return url_for("driver_portal.dashboard")
    return url_for("main.dashboard")


def _is_safe_url(target):
    """Return True only for same-site relative redirect targets.

    Flask-Login's `login_view` redirect appends the requested path as
    `?next=...`. We must never honor an absolute/external URL there, since
    `redirect(next)` on `//evil.com` would send a just-logged-in staff member
    off-site (open redirect). Only relative, single-slash paths are allowed.
    """
    if not target:
        return False
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and ref.netloc == test.netloc


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_default_landing_page(current_user))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.check_password(form.password.data):
            if not user.is_active_user:
                flash("This account has been deactivated. Contact your administrator.", "danger")
                return render_template("auth/login.html", form=form)
            login_user(user, remember=form.remember.data)
            user.last_login = datetime.utcnow()
            db.session.commit()
            next_page = request.args.get("next")
            # Guard against open redirect: only honor same-site relative URLs.
            if next_page and not _is_safe_url(next_page):
                next_page = None
            flash("Welcome back!", "success")
            return redirect(next_page or _default_landing_page(user))
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html", form=form)


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    # Logging out returns staff to the PUBLIC landing page (two-entrance
    # gateway), not the staff login screen. The office area remains
    # blocked: any internal URL now requires login again.
    return redirect(url_for("public.home"))


@auth.route("/reset-password", methods=["GET", "POST"])
def reset_password_request():
    """Password reset request — generates a token. Email sending is stubbed for dev."""
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            # In production, send email with reset link:
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            subject, body = f"Password Reset - {get_company_settings().company_name}", \
                f"Click the following link to reset your password:\n\n{reset_url}\n\nThis link expires in 1 hour."
            send_email(user.email, subject, body)
            flash("If that email exists, a reset link has been sent.", "info")
        else:
            flash("If that email exists, a reset link has been sent.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password_request.html", form=form)


@auth.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Reset password with a valid token."""
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
        flash("The reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.reset_password_request"))

    form = PasswordResetForm()
    if form.validate_on_submit():
        if form.password.data != form.confirm.data:
            flash("Passwords do not match.", "danger")
            return render_template("auth/reset_password.html", form=form)
        user.set_password(form.password.data)
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()
        flash("Your password has been reset. Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form)


@auth.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "danger")
            return render_template("auth/change_password.html", form=form)
        if form.new_password.data != form.confirm.data:
            flash("New passwords do not match.", "danger")
            return render_template("auth/change_password.html", form=form)
        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash("Password changed successfully.", "success")
        return redirect(url_for("main.settings"))
    return render_template("auth/change_password.html", form=form)
