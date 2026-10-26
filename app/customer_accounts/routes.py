from datetime import datetime, timedelta
import hashlib
import secrets

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms import CustomerAccountRequestForm, CustomerAccountReviewForm, CustomerInvitationForm
from app.models import Contact, Customer, CustomerAccountRequest, CustomerInvitation, User
from app.utils import admin_required, send_email

customer_accounts = Blueprint("customer_accounts", __name__)


@customer_accounts.route("/request", methods=["GET", "POST"])
def request_access():
    form = CustomerAccountRequestForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        # Generic acknowledgement avoids disclosing whether a login exists.
        if not User.query.filter_by(email=email).first():
            db.session.add(CustomerAccountRequest(
                business_name=form.business_name.data.strip(),
                contact_name=form.contact_name.data.strip(), email=email,
                phone=form.phone.data.strip(),
            ))
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
        return render_template("customer_accounts/request_received.html"), 202
    return render_template("customer_accounts/request.html", form=form)


@customer_accounts.route("/admin", methods=["GET"])
@login_required
@admin_required
def queue():
    requests = CustomerAccountRequest.query.order_by(CustomerAccountRequest.created_at.desc()).all()
    return render_template("customer_accounts/admin_queue.html", requests=requests)


@customer_accounts.route("/admin/<int:request_id>", methods=["GET", "POST"])
@login_required
@admin_required
def review(request_id):
    account_request = db.session.get(CustomerAccountRequest, request_id)
    if not account_request:
        abort(404)
    if account_request.status != "pending":
        flash("This request has already been reviewed.", "info")
        return redirect(url_for("customer_accounts.queue"))
    form = CustomerAccountReviewForm()
    form.customer_id.choices = [(0, "Create a new customer record for this facility")] + [
        (c.id, f"{c.business_name} (#{c.id})") for c in Customer.query.order_by(Customer.business_name).all()
    ]
    if form.validate_on_submit():
        if form.customer_id.data is None:
            abort(400)
        customer = db.session.get(Customer, form.customer_id.data) if form.customer_id.data else None
        if form.customer_id.data not in (None, 0) and not customer:
            abort(400)
        if form.customer_id.data == 0:
            customer = Customer(business_name=account_request.business_name, category="Other", status="active")
            db.session.add(customer)
            db.session.flush()
        email = account_request.email.lower()
        if User.query.filter_by(email=email).first():
            flash("That email already belongs to an account; resolve it before approval.", "danger")
            return render_template("customer_accounts/admin_review.html", form=form, account_request=account_request)
        token = secrets.token_urlsafe(32)
        user = User(email=email, first_name=account_request.contact_name, phone=account_request.phone,
                    role="customer", customer_id=customer.id, is_active_user=False)
        user.set_password(secrets.token_urlsafe(32))
        db.session.add(user)
        db.session.flush()
        if not Contact.query.filter_by(customer_id=customer.id, email=email).first():
            db.session.add(Contact(customer_id=customer.id, name=account_request.contact_name,
                                   email=email, phone=account_request.phone,
                                   is_primary=not bool(customer.contacts)))
        invitation = CustomerInvitation(user_id=user.id, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                                        expires_at=datetime.utcnow() + timedelta(hours=48))
        db.session.add(invitation)
        db.session.flush()
        changed = CustomerAccountRequest.query.filter_by(id=account_request.id, status="pending").update({
            "status": "approved", "customer_id": customer.id, "user_id": user.id,
            "reviewed_by_id": current_user.id, "reviewed_at": datetime.utcnow(),
            "review_reason": form.review_reason.data.strip() if form.review_reason.data else None,
        }, synchronize_session=False)
        if changed != 1:
            db.session.rollback()
            abort(409)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("This request could not be approved because its account changed. Refresh and review it again.", "danger")
            return redirect(url_for("customer_accounts.queue"))
        invite_url = url_for("customer_accounts.activate", token=token, _external=True)
        sent = send_email(email, "Triple Force customer portal invitation",
                          f"Your access request was approved. Set your password within 48 hours:\n\n{invite_url}")
        if not sent:
            flash("Account approved, but the invitation email failed. Use Resend invitation after correcting mail delivery.", "warning")
        else:
            flash("Request approved and invitation sent.", "success")
        return redirect(url_for("customer_accounts.queue"))
    return render_template("customer_accounts/admin_review.html", form=form, account_request=account_request)


@customer_accounts.route("/admin/<int:request_id>/resend", methods=["POST"])
@login_required
@admin_required
def resend_invitation(request_id):
    account_request = db.session.get(CustomerAccountRequest, request_id)
    if not account_request or account_request.status != "approved" or not account_request.user_id:
        abort(404)
    user = db.session.get(User, account_request.user_id)
    if not user or user.role != "customer" or user.is_active_user or not user.customer_id:
        abort(409)
    token = secrets.token_urlsafe(32)
    invitation = CustomerInvitation.query.filter_by(user_id=user.id).first()
    if invitation is None:
        invitation = CustomerInvitation(user_id=user.id, token_hash="", expires_at=datetime.utcnow())
        db.session.add(invitation)
    invitation.token_hash = hashlib.sha256(token.encode()).hexdigest()
    invitation.expires_at = datetime.utcnow() + timedelta(hours=48)
    invitation.redeemed_at = None
    invitation.created_at = datetime.utcnow()
    db.session.commit()
    invite_url = url_for("customer_accounts.activate", token=token, _external=True)
    if send_email(user.email, "Triple Force customer portal invitation",
                  f"Your customer portal invitation is ready. Set your password within 48 hours:\n\n{invite_url}"):
        flash("Invitation resent.", "success")
    else:
        flash("Invitation email could not be sent. Check mail configuration before retrying.", "danger")
    return redirect(url_for("customer_accounts.queue"))


@customer_accounts.route("/admin/<int:request_id>/reject", methods=["POST"])
@login_required
@admin_required
def reject(request_id):
    account_request = db.session.get(CustomerAccountRequest, request_id)
    if not account_request:
        abort(404)
    if account_request.status != "pending":
        abort(409)
    changed = CustomerAccountRequest.query.filter_by(id=account_request.id, status="pending").update({
        "status": "rejected", "reviewed_by_id": current_user.id, "reviewed_at": datetime.utcnow(),
    }, synchronize_session=False)
    if changed != 1:
        db.session.rollback()
        abort(409)
    db.session.commit()
    flash("Request rejected.", "info")
    return redirect(url_for("customer_accounts.queue"))


@customer_accounts.route("/activate/<token>", methods=["GET", "POST"])
def activate(token):
    invitation = CustomerInvitation.query.filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest()).first()
    if not invitation or invitation.redeemed_at or invitation.expires_at < datetime.utcnow():
        abort(404)
    user = db.session.get(User, invitation.user_id)
    if not user or user.role != "customer" or not user.customer_id or user.is_active_user:
        abort(404)
    form = CustomerInvitationForm()
    if form.validate_on_submit():
        if form.password.data != form.confirm.data:
            form.password.errors.append("Passwords do not match.")
        else:
            now = datetime.utcnow()
            changed = CustomerInvitation.query.filter_by(id=invitation.id, redeemed_at=None).filter(
                CustomerInvitation.expires_at > now
            ).update({"redeemed_at": now}, synchronize_session=False)
            if changed != 1:
                db.session.rollback()
                abort(404)
            user.set_password(form.password.data)
            user.is_active_user = True
            db.session.commit()
            flash("Account activated. Please sign in.", "success")
            return redirect(url_for("auth.login"))
    return render_template("customer_accounts/activate.html", form=form)
