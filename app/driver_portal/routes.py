"""Driver Portal routes — driver-facing views scoped to their own assigned deliveries."""
from datetime import datetime, date

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import (
    Delivery, DeliveryStatusHistory, ProofOfDelivery, ChainOfCustody,
    Driver, DELIVERY_STATUSES,
)
from app.forms import DeliveryStatusUpdateForm, DriverPODForm, ChainOfCustodyForm
from app.utils import driver_or_above, send_email, get_company_settings

driver_portal = Blueprint("driver_portal", __name__)

# Statuses a driver is allowed to progress a delivery through (no admin-only states)
DRIVER_STATUS_FLOW = [
    "En Route to Pickup", "Arrived at Pickup", "Picked Up",
    "In Transit", "Arrived at Delivery", "Delivered", "Completed",
]


def _get_current_driver():
    """Resolve the Driver record linked to the logged-in user."""
    if current_user.driver_record_id:
        return db.session.get(Driver, current_user.driver_record_id)
    # Fallback: match by email
    return Driver.query.filter_by(email=current_user.email).first()


@driver_portal.route("/")
@login_required
@driver_or_above
def dashboard():
    """Driver dashboard — shows only deliveries assigned to the logged-in driver."""
    driver = _get_current_driver()
    if not driver:
        flash("No driver profile is linked to your account. Contact your administrator.", "warning")
        return render_template("driver_portal/dashboard.html", driver=None, deliveries=[], today_count=0, active_count=0, completed_count=0)

    today = date.today()
    all_assigned = Delivery.query.filter(Delivery.driver_id == driver.id).order_by(
        Delivery.pickup_datetime.asc()
    ).all()

    active = [d for d in all_assigned if d.status not in ("Delivered", "Completed", "Cancelled")]
    completed_today = [
        d for d in all_assigned
        if d.status in ("Delivered", "Completed") and d.actual_delivery_time and d.actual_delivery_time.date() == today
    ]

    return render_template(
        "driver_portal/dashboard.html",
        driver=driver,
        deliveries=active,
        today_count=len([d for d in all_assigned if d.pickup_datetime and d.pickup_datetime.date() == today]),
        active_count=len(active),
        completed_count=len(completed_today),
    )


@driver_portal.route("/deliveries/<int:delivery_id>", methods=["GET", "POST"])
@login_required
@driver_or_above
def delivery_detail(delivery_id):
    """Driver's view of a single assigned delivery — status updates, POD, chain of custody."""
    delivery = db.session.get(Delivery, delivery_id)
    if not delivery:
        abort(404)

    driver = _get_current_driver()
    # Enforce that drivers can only see their own assigned deliveries (admins/dispatchers can see all)
    if current_user.role == "driver":
        if not driver or delivery.driver_id != driver.id:
            abort(403)

    status_form = DeliveryStatusUpdateForm()
    status_form.status.choices = [(s, s) for s in DRIVER_STATUS_FLOW]

    if status_form.validate_on_submit() and status_form.submit.data:
        old_status = delivery.status
        delivery.status = status_form.status.data
        delivery.updated_at = datetime.utcnow()

        if status_form.status.data == "Picked Up" and not delivery.actual_pickup_time:
            delivery.actual_pickup_time = datetime.utcnow()
        if status_form.status.data in ("Delivered", "Completed") and not delivery.actual_delivery_time:
            delivery.actual_delivery_time = datetime.utcnow()

        history = DeliveryStatusHistory(
            delivery_id=delivery.id,
            status=status_form.status.data,
            notes=status_form.notes.data,
            updated_by=current_user.full_name or current_user.email,
        )
        db.session.add(history)
        db.session.commit()
        flash(f"Status updated: {old_status} \u2192 {status_form.status.data}", "success")
        return redirect(url_for("driver_portal.delivery_detail", delivery_id=delivery.id))

    return render_template(
        "driver_portal/delivery_detail.html",
        delivery=delivery,
        status_form=status_form,
    )


@driver_portal.route("/deliveries/<int:delivery_id>/pod", methods=["GET", "POST"])
@login_required
@driver_or_above
def submit_pod(delivery_id):
    """Driver submits Proof of Delivery for an assigned delivery."""
    delivery = db.session.get(Delivery, delivery_id)
    if not delivery:
        abort(404)

    driver = _get_current_driver()
    if current_user.role == "driver":
        if not driver or delivery.driver_id != driver.id:
            abort(403)

    form = DriverPODForm()
    if not form.is_submitted():
        form.delivery_date.data = date.today()

    if form.validate_on_submit():
        pod = delivery.pod or ProofOfDelivery(delivery_id=delivery.id)
        pod.recipient_name = form.recipient_name.data
        pod.delivery_date = form.delivery_date.data
        pod.delivery_time = datetime.utcnow().time()
        pod.driver_name = driver.name if driver else current_user.full_name
        pod.notes = form.notes.data
        pod.refused = form.refused.data
        pod.refusal_reason = form.refusal_reason.data
        pod.timestamp = datetime.utcnow()

        db.session.add(pod)

        if not form.refused.data:
            delivery.status = "Delivered"
            if not delivery.actual_delivery_time:
                delivery.actual_delivery_time = datetime.utcnow()

        history = DeliveryStatusHistory(
            delivery_id=delivery.id,
            status="Delivered" if not form.refused.data else "Delivery Refused",
            notes=f"POD captured by {current_user.full_name or current_user.email}",
            updated_by=current_user.full_name or current_user.email,
        )
        db.session.add(history)
        db.session.commit()

        # Notify dispatch via email (best-effort, non-blocking on failure)
        try:
            settings = get_company_settings()
            send_email(
                settings.email,
                f"POD Captured — Order {delivery.order_number}",
                f"Proof of delivery has been captured for order {delivery.order_number} by {current_user.full_name or current_user.email}.",
            )
        except Exception:
            pass

        flash("Proof of delivery submitted successfully.", "success")
        return redirect(url_for("driver_portal.delivery_detail", delivery_id=delivery.id))

    return render_template("driver_portal/pod_form.html", delivery=delivery, form=form)


@driver_portal.route("/deliveries/<int:delivery_id>/custody", methods=["GET", "POST"])
@login_required
@driver_or_above
def submit_custody(delivery_id):
    """Driver adds a chain-of-custody record for a medical courier delivery."""
    delivery = db.session.get(Delivery, delivery_id)
    if not delivery:
        abort(404)

    driver = _get_current_driver()
    if current_user.role == "driver":
        if not driver or delivery.driver_id != driver.id:
            abort(403)

    form = ChainOfCustodyForm()
    if form.validate_on_submit():
        record = ChainOfCustody(
            delivery_id=delivery.id,
            person_releasing=form.person_releasing.data,
            person_accepting=form.person_accepting.data,
            release_time=datetime.utcnow(),
            acceptance_time=datetime.utcnow(),
            temperature=form.temperature.data,
            tamper_seal=form.tamper_seal.data,
            package_condition=form.package_condition.data,
            incident_report=form.incident_report.data,
        )
        db.session.add(record)
        db.session.commit()
        flash("Chain of custody record added.", "success")
        return redirect(url_for("driver_portal.delivery_detail", delivery_id=delivery.id))

    return render_template("driver_portal/custody_form.html", delivery=delivery, form=form)
