"""Dispatch blueprint: delivery board, tracking, proof of delivery, chain of custody."""
import base64
import os
from datetime import datetime, date
from io import BytesIO

from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file, current_app, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models import (
    Delivery, DeliveryStatusHistory, ProofOfDelivery, ChainOfCustody,
    Customer, Driver, Quote, DELIVERY_STATUSES,
)
from app.forms import DeliveryForm, DeliveryStatusForm, ProofOfDeliveryForm, ChainOfCustodyForm
from app.utils import (
    dispatcher_or_above,
    get_next_order_number, get_company_settings, save_uploaded_file,
    generate_pod_pdf, send_email, render_email_template,
)

dispatch = Blueprint("dispatch", __name__)


# ═══════════════════════════════════════════════════════════════
#  DISPATCH BOARD
# ═══════════════════════════════════════════════════════════════
@dispatch.route("/")
@login_required
@dispatcher_or_above
def board():
    view = request.args.get("view", "board")  # board, list, calendar
    status_filter = request.args.get("status", "")
    driver_filter = request.args.get("driver", "")
    date_filter = request.args.get("date", "")

    query = Delivery.query
    if status_filter:
        query = query.filter(Delivery.status == status_filter)
    if driver_filter:
        query = query.filter(Delivery.driver_id == int(driver_filter))

    deliveries = query.order_by(Delivery.created_at.desc()).limit(100).all()
    drivers = Driver.query.filter_by(is_active=True).all()

    # Group by status for board view
    grouped = {}
    for s in DELIVERY_STATUSES:
        grouped[s] = [d for d in deliveries if d.status == s]

    return render_template("dispatch/board.html",
        deliveries=deliveries, grouped=grouped, drivers=drivers,
        statuses=DELIVERY_STATUSES, view=view,
        status_filter=status_filter, driver_filter=driver_filter,
    )


@dispatch.route("/new", methods=["GET", "POST"])
@login_required
@dispatcher_or_above
def new_delivery():
    form = DeliveryForm()
    customers = Customer.query.filter_by(is_archived=False).order_by(Customer.business_name).all()
    form.customer_id.choices = [(0, "— Select Customer —")] + [(c.id, c.business_name) for c in customers]
    drivers = Driver.query.filter_by(is_active=True).all()
    form.driver_id.choices = [(0, "— Unassigned —")] + [(d.id, d.name) for d in drivers]

    if form.validate_on_submit():
        order_number = get_next_order_number()
        customer_id = form.customer_id.data if form.customer_id.data and form.customer_id.data > 0 else None
        driver_id = form.driver_id.data if form.driver_id.data and form.driver_id.data > 0 else None

        delivery = Delivery(
            order_number=order_number,
            customer_id=customer_id,
            quote_id=form.quote_id.data if form.quote_id.data else None,
            pickup_contact=form.pickup_contact.data,
            pickup_address=form.pickup_address.data,
            pickup_instructions=form.pickup_instructions.data,
            pickup_datetime=form.pickup_datetime.data,
            delivery_contact=form.delivery_contact.data,
            delivery_address=form.delivery_address.data,
            delivery_instructions=form.delivery_instructions.data,
            delivery_deadline=form.delivery_deadline.data,
            service_type=form.service_type.data,
            package_type=form.package_type.data,
            quantity=form.quantity.data,
            special_handling=form.special_handling.data,
            mileage=form.mileage.data,
            driver_id=driver_id,
            quote_amount=form.quote_amount.data,
            internal_notes=form.internal_notes.data,
            customer_notes=form.customer_notes.data,
            requires_chain_of_custody=form.requires_chain_of_custody.data,
            requires_pod=form.requires_pod.data,
            is_medical=form.is_medical.data,
            specimen_id=form.specimen_id.data,
            pickup_facility=form.pickup_facility.data,
            delivery_facility=form.delivery_facility.data,
            temperature_requirement=form.temperature_requirement.data,
            tamper_seal_number=form.tamper_seal_number.data,
            created_by=current_user.id,
            status="New Request",
        )
        db.session.add(delivery)

        history = DeliveryStatusHistory(
            delivery=delivery,
            status="New Request",
            notes="Delivery created",
            updated_by=current_user.full_name or current_user.email,
        )
        db.session.add(history)
        db.session.commit()

        # If driver assigned, update status
        if driver_id:
            delivery.status = "Driver Assigned"
            h = DeliveryStatusHistory(delivery=delivery, status="Driver Assigned",
                                      updated_by=current_user.full_name or current_user.email)
            db.session.add(h)
            db.session.commit()

        flash(f"Delivery {order_number} created.", "success")
        return redirect(url_for("dispatch.detail", delivery_id=delivery.id))

    return render_template("dispatch/form.html", form=form, title="New Delivery Order")


@dispatch.route("/<int:delivery_id>")
@login_required
@dispatcher_or_above
def detail(delivery_id):
    delivery = Delivery.query.get_or_404(delivery_id)
    status_form = DeliveryStatusForm()

    # Default the "Update Status" dropdown to the next logical step in the
    # delivery workflow (DELIVERY_STATUSES order) instead of always
    # resetting to the first choice ("New Request"). Terminal states
    # (Completed / Cancelled) keep showing the current status.
    terminal = ("Completed", "Cancelled")
    current = delivery.status or "New Request"
    if current in terminal:
        next_status = current
    elif current in DELIVERY_STATUSES:
        idx = DELIVERY_STATUSES.index(current)
        next_status = DELIVERY_STATUSES[idx + 1] if idx + 1 < len(DELIVERY_STATUSES) else current
    else:
        next_status = current
    status_form.status.data = next_status

    pod_form = ProofOfDeliveryForm()
    coc_form = ChainOfCustodyForm()

    # Set actual times if delivered
    if not pod_form.delivery_date.data:
        pod_form.delivery_date.data = date.today()
    if delivery.driver:
        pod_form.driver_name.data = delivery.driver.name

    return render_template("dispatch/detail.html",
        delivery=delivery, status_form=status_form,
        pod_form=pod_form, coc_form=coc_form,
        statuses=DELIVERY_STATUSES,
    )


@dispatch.route("/<int:delivery_id>/edit", methods=["GET", "POST"])
@login_required
@dispatcher_or_above
def edit(delivery_id):
    delivery = Delivery.query.get_or_404(delivery_id)
    form = DeliveryForm(obj=delivery)
    customers = Customer.query.filter_by(is_archived=False).order_by(Customer.business_name).all()
    form.customer_id.choices = [(0, "— Select Customer —")] + [(c.id, c.business_name) for c in customers]
    drivers = Driver.query.filter_by(is_active=True).all()
    form.driver_id.choices = [(0, "— Unassigned —")] + [(d.id, d.name) for d in drivers]

    if form.validate_on_submit():
        customer_id = form.customer_id.data if form.customer_id.data and form.customer_id.data > 0 else None
        driver_id = form.driver_id.data if form.driver_id.data and form.driver_id.data > 0 else None

        delivery.customer_id = customer_id
        delivery.pickup_contact = form.pickup_contact.data
        delivery.pickup_address = form.pickup_address.data
        delivery.pickup_instructions = form.pickup_instructions.data
        delivery.pickup_datetime = form.pickup_datetime.data
        delivery.delivery_contact = form.delivery_contact.data
        delivery.delivery_address = form.delivery_address.data
        delivery.delivery_instructions = form.delivery_instructions.data
        delivery.delivery_deadline = form.delivery_deadline.data
        delivery.service_type = form.service_type.data
        delivery.package_type = form.package_type.data
        delivery.quantity = form.quantity.data
        delivery.special_handling = form.special_handling.data
        delivery.mileage = form.mileage.data
        delivery.driver_id = driver_id
        delivery.quote_amount = form.quote_amount.data
        delivery.internal_notes = form.internal_notes.data
        delivery.customer_notes = form.customer_notes.data
        delivery.requires_chain_of_custody = form.requires_chain_of_custody.data
        delivery.requires_pod = form.requires_pod.data
        delivery.is_medical = form.is_medical.data
        delivery.specimen_id = form.specimen_id.data
        delivery.pickup_facility = form.pickup_facility.data
        delivery.delivery_facility = form.delivery_facility.data
        delivery.temperature_requirement = form.temperature_requirement.data
        delivery.tamper_seal_number = form.tamper_seal_number.data
        db.session.commit()
        flash("Delivery updated.", "success")
        return redirect(url_for("dispatch.detail", delivery_id=delivery_id))

    return render_template("dispatch/form.html", form=form, title="Edit Delivery", delivery=delivery)


@dispatch.route("/<int:delivery_id>/status", methods=["POST"])
@login_required
@dispatcher_or_above
def update_status(delivery_id):
    delivery = Delivery.query.get_or_404(delivery_id)
    form = DeliveryStatusForm()
    if form.validate_on_submit():
        delivery.status = form.status.data

        # Auto-set actual times
        if form.status.data == "Picked Up" and not delivery.actual_pickup_time:
            delivery.actual_pickup_time = datetime.utcnow()
        if form.status.data in ("Delivered", "Completed") and not delivery.actual_delivery_time:
            delivery.actual_delivery_time = datetime.utcnow()
        if form.status.data == "Completed" and not delivery.actual_delivery_time:
            delivery.actual_delivery_time = datetime.utcnow()

        history = DeliveryStatusHistory(
            delivery=delivery,
            status=form.status.data,
            notes=form.notes.data,
            latitude=form.latitude.data if form.latitude.data else None,
            longitude=form.longitude.data if form.longitude.data else None,
            updated_by=current_user.full_name or current_user.email,
        )
        db.session.add(history)
        db.session.commit()
        flash(f"Status updated to: {form.status.data}", "success")

        # Send notification email if customer has email
        if delivery.customer and delivery.customer.primary_contact and delivery.customer.primary_contact.email:
            template_map = {
                "Driver Assigned": "driver_assigned",
                "Picked Up": "pickup_completed",
                "In Transit": "delivery_in_progress",
                "Delivered": "delivery_completed",
                "Completed": "delivery_completed",
            }
            tmpl = template_map.get(form.status.data)
            if tmpl:
                subject, body = render_email_template(tmpl, {
                    "customer_name": delivery.customer.business_name,
                    "order_number": delivery.order_number,
                })
                send_email(delivery.customer.primary_contact.email, subject, body)

    return redirect(url_for("dispatch.detail", delivery_id=delivery_id))


# ═══════════════════════════════════════════════════════════════
#  PROOF OF DELIVERY
# ═══════════════════════════════════════════════════════════════
@dispatch.route("/<int:delivery_id>/pod", methods=["POST"])
@login_required
@dispatcher_or_above
def submit_pod(delivery_id):
    delivery = Delivery.query.get_or_404(delivery_id)
    form = ProofOfDeliveryForm()

    if form.validate_on_submit():
        # Parse time string
        delivery_time = None
        if form.delivery_time.data:
            try:
                delivery_time = datetime.strptime(form.delivery_time.data, "%H:%M").time()
            except ValueError:
                pass

        # Handle signature (base64 PNG from canvas)
        signature_filename = None
        if form.signature_data.data:
            signature_filename = save_signature(form.signature_data.data, delivery.order_number)

        # Handle photo upload
        photo_filename = None
        if form.photo.data:
            photo_filename = save_uploaded_file(form.photo.data, subfolder="pod_photos")

        # Parse GPS
        lat = float(form.gps_latitude.data) if form.gps_latitude.data else None
        lng = float(form.gps_longitude.data) if form.gps_longitude.data else None

        pod = ProofOfDelivery(
            delivery_id=delivery_id,
            recipient_name=form.recipient_name.data,
            signature_filename=signature_filename,
            photo_filename=photo_filename,
            delivery_date=form.delivery_date.data,
            delivery_time=delivery_time,
            driver_name=form.driver_name.data,
            notes=form.notes.data,
            refused=form.refused.data,
            refusal_reason=form.refusal_reason.data,
            exception_reason=form.exception_reason.data,
            gps_latitude=lat,
            gps_longitude=lng,
        )
        db.session.add(pod)

        # Update delivery status
        if form.refused.data:
            delivery.status = "Cancelled"
        else:
            delivery.status = "Delivered"
            delivery.actual_delivery_time = datetime.utcnow()

        history = DeliveryStatusHistory(
            delivery=delivery,
            status=delivery.status,
            notes=f"POD submitted by {form.driver_name.data or current_user.full_name}",
            updated_by=current_user.full_name or current_user.email,
        )
        db.session.add(history)
        db.session.commit()

        flash("Proof of delivery recorded.", "success")
    else:
        for field, errors in form.errors.items():
            for e in errors:
                flash(f"{field}: {e}", "danger")

    return redirect(url_for("dispatch.detail", delivery_id=delivery_id))


@dispatch.route("/<int:delivery_id>/pod/pdf")
@login_required
@dispatcher_or_above
def pod_pdf(delivery_id):
    delivery = Delivery.query.get_or_404(delivery_id)
    settings = get_company_settings()
    buf = generate_pod_pdf(delivery, settings)
    return send_file(buf, as_attachment=True, download_name=f"POD_{delivery.order_number}.pdf",
                     mimetype="application/pdf")


@dispatch.route("/<int:delivery_id>/pod/email", methods=["POST"])
@login_required
@dispatcher_or_above
def email_pod(delivery_id):
    delivery = Delivery.query.get_or_404(delivery_id)
    to = request.form.get("email")
    if not to and delivery.customer and delivery.customer.primary_contact:
        to = delivery.customer.primary_contact.email
    if not to:
        flash("No email address available.", "danger")
        return redirect(url_for("dispatch.detail", delivery_id=delivery_id))

    settings = get_company_settings()
    subject, body = render_email_template("proof_of_delivery", {
        "customer_name": delivery.customer.business_name if delivery.customer else "Customer",
        "order_number": delivery.order_number,
    })
    buf = generate_pod_pdf(delivery, settings)
    attachments = [(f"POD_{delivery.order_number}.pdf", "application/pdf", buf.getvalue())]
    success = send_email(to, subject, body, attachments=attachments)
    if success:
        flash(f"POD emailed to {to}.", "success")
    else:
        flash("Email could not be sent. Check mail settings.", "warning")
    return redirect(url_for("dispatch.detail", delivery_id=delivery_id))


# ═══════════════════════════════════════════════════════════════
#  CHAIN OF CUSTODY
# ═══════════════════════════════════════════════════════════════
@dispatch.route("/<int:delivery_id>/chain-of-custody", methods=["POST"])
@login_required
@dispatcher_or_above
def add_coc_entry(delivery_id):
    delivery = Delivery.query.get_or_404(delivery_id)
    form = ChainOfCustodyForm()
    if form.validate_on_submit():
        entry = ChainOfCustody(
            delivery_id=delivery_id,
            person_releasing=form.person_releasing.data,
            person_accepting=form.person_accepting.data,
            release_time=form.release_time.data,
            acceptance_time=form.acceptance_time.data,
            temperature=form.temperature.data,
            tamper_seal=form.tamper_seal.data,
            package_condition=form.package_condition.data,
            incident_report=form.incident_report.data,
            driver_acknowledged=form.driver_acknowledged.data,
            driver_acknowledgment_time=datetime.utcnow() if form.driver_acknowledged.data else None,
        )
        db.session.add(entry)

        # Update medical courier temp fields
        if form.temperature.data is not None:
            if not delivery.temp_at_pickup:
                delivery.temp_at_pickup = form.temperature.data
            else:
                delivery.temp_at_delivery = form.temperature.data
        if form.tamper_seal.data:
            delivery.tamper_seal_number = form.tamper_seal.data

        db.session.commit()
        flash("Chain of custody entry added.", "success")
    else:
        for field, errors in form.errors.items():
            for e in errors:
                flash(f"{field}: {e}", "danger")
    return redirect(url_for("dispatch.detail", delivery_id=delivery_id))


# ═══════════════════════════════════════════════════════════════
#  HELPER: Save signature image
# ═══════════════════════════════════════════════════════════════
def save_signature(data_url, order_number):
    """Save a base64 signature image from canvas."""
    try:
        # Remove data:image/png;base64, prefix
        header, encoded = data_url.split(",", 1)
        img_data = base64.b64decode(encoded)

        filename = f"sig_{order_number}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], "signatures", filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(img_data)
        return filename
    except Exception as e:
        current_app.logger.error(f"Signature save failed: {e}")
        return None
