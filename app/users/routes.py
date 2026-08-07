"""User management routes — admin-only CRUD for system users with roles."""
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import User, Driver
from app.forms import UserForm, UserEditForm
from app.utils import admin_required

users = Blueprint("users", __name__)


@users.route("/")
@login_required
@admin_required
def index():
    """List all system users."""
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template("users/index.html", users=all_users)


@users.route("/new", methods=["GET", "POST"])
@login_required
@admin_required
def create():
    """Create a new user account."""
    form = UserForm()
    if form.validate_on_submit():
        existing = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if existing:
            flash("A user with that email already exists.", "danger")
            return render_template("users/form.html", form=form, is_edit=False)

        user = User(
            email=form.email.data.strip().lower(),
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            phone=form.phone.data,
            role=form.role.data,
            is_active_user=form.is_active_user.data,
        )
        user.set_password(form.password.data)

        # If role is driver, link to an existing Driver record by email
        if user.role == "driver":
            driver = Driver.query.filter_by(email=user.email).first()
            if driver:
                user.driver_record_id = driver.id
            else:
                # Create a Driver record automatically
                driver = Driver(
                    name=f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
                    email=user.email,
                )
                db.session.add(driver)
                db.session.flush()
                user.driver_record_id = driver.id

        db.session.add(user)
        db.session.commit()
        flash(f"User '{user.email}' created successfully.", "success")
        return redirect(url_for("users.index"))

    return render_template("users/form.html", form=form, is_edit=False)


@users.route("/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit(user_id):
    """Edit an existing user account."""
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    form = UserEditForm(obj=user)
    if form.validate_on_submit():
        # Prevent deactivating yourself
        if user.id == current_user.id and not form.is_active_user.data:
            flash("You cannot deactivate your own account.", "danger")
            return render_template("users/form.html", form=form, is_edit=True, user=user)

        email_taken = User.query.filter(
            User.email == form.email.data.strip().lower(),
            User.id != user.id,
        ).first()
        if email_taken:
            flash("That email is already used by another account.", "danger")
            return render_template("users/form.html", form=form, is_edit=True, user=user)

        user.email = form.email.data.strip().lower()
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.phone = form.phone.data
        user.role = form.role.data
        user.is_active_user = form.is_active_user.data

        # If new password provided, update it
        if form.new_password.data:
            user.set_password(form.new_password.data)

        # If role changed to driver, link/create Driver record
        if user.role == "driver" and not user.driver_record_id:
            driver = Driver.query.filter_by(email=user.email).first()
            if not driver:
                driver = Driver(
                    name=f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
                    email=user.email,
                )
                db.session.add(driver)
                db.session.flush()
            user.driver_record_id = driver.id

        db.session.commit()
        flash(f"User '{user.email}' updated successfully.", "success")
        return redirect(url_for("users.index"))

    return render_template("users/form.html", form=form, is_edit=True, user=user)


@users.route("/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@admin_required
def toggle_active(user_id):
    """Activate/deactivate a user account."""
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "danger")
        return redirect(url_for("users.index"))

    user.is_active_user = not user.is_active_user
    db.session.commit()
    status = "activated" if user.is_active_user else "deactivated"
    flash(f"User '{user.email}' has been {status}.", "info")
    return redirect(url_for("users.index"))
