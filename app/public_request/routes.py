"""Public customer-facing routes (no login required, no internal navigation).

These routes are intentionally separate from the staff `main`/`dispatch`
blueprints so they never inherit the internal sidebar or admin navigation,
regardless of whether a staff member happens to be logged in.
"""
from flask import (
    Blueprint, render_template, request, flash, redirect, url_for, current_app,
)
from app.extensions import db
from app.models import Delivery, DeliveryStatusHistory
from app.forms import CustomerPickupRequestForm
from app.utils import get_next_order_number, get_company_settings

public = Blueprint("public", __name__)


@public.route("/request-pickup", methods=["GET", "POST"])
def request_pickup():
    """Public page where customers request a pickup.

    Renders only the customer pickup request form — no sidebar, no admin
    navigation, no dashboard tools. On a valid submission it creates a
    Delivery record (status "New Request") and shows a confirmation with
    the generated order number. Internal staff pages remain unchanged and
    protected behind the existing login/role system.
    """
    form = CustomerPickupRequestForm()
    settings = get_company_settings()
    company_name = settings.company_name if settings else "Triple Force Logistic LLC"

    if form.validate_on_submit():
        order_number = get_next_order_number()

        # Build a structured "requested by" block so dispatch can see who
        # placed the request even though there is no logged-in user.
        requested_by = "Requested by: {} | Phone: {}".format(
            form.requester_name.data, form.requester_phone.data
        )
        if form.requester_email.data:
            requested_by += " | Email: {}".format(form.requester_email.data)

        existing_notes = (form.customer_notes.data or "").strip()
        customer_notes = requested_by + ("\n\n" + existing_notes if existing_notes else "")

        # Fall back to the requester when no separate pickup/delivery contact
        # was provided, so the record always has a contactable person.
        requester_contact = "{} — {}".format(
            form.requester_name.data, form.requester_phone.data
        )

        delivery = Delivery(
            order_number=order_number,
            customer_id=None,  # public submission — not linked to a Customer record
            pickup_contact=form.pickup_contact.data or requester_contact,
            pickup_address=form.pickup_address.data,
            pickup_instructions=form.pickup_instructions.data,
            pickup_datetime=form.pickup_datetime.data,
            delivery_contact=form.delivery_contact.data or form.requester_name.data,
            delivery_address=form.delivery_address.data,
            delivery_instructions=form.delivery_instructions.data,
            service_type=form.service_type.data,
            package_type=form.package_type.data,
            quantity=form.quantity.data or 1,
            special_handling=form.special_handling.data,
            is_medical=form.is_medical.data,
            pickup_facility=form.pickup_facility.data,
            delivery_facility=form.delivery_facility.data,
            temperature_requirement=form.temperature_requirement.data,
            customer_notes=customer_notes,
            created_by=None,  # no logged-in staff user for public submissions
            status="New Request",
        )
        db.session.add(delivery)
        db.session.commit()

        # Best-effort internal notification email. Never blocks the request
        # and never rolls back the delivery on failure.
        try:
            from app.utils import send_email
            notify_to = settings.email if settings else current_app.config.get("MAIL_DEFAULT_SENDER")
            if notify_to:
                body = (
                    "A new pickup request was submitted from the website.\n\n"
                    "Order #: {}\n"
                    "Requested by: {}\n"
                    "Phone: {}\n"
                    "Pickup: {}\n"
                    "Delivery: {}\n"
                    "Service: {}\n".format(
                        order_number,
                        form.requester_name.data,
                        form.requester_phone.data,
                        form.pickup_address.data,
                        form.delivery_address.data,
                        form.service_type.data,
                    )
                )
                send_email(notify_to, "New Pickup Request — {}".format(order_number), body)
        except Exception as e:  # pragma: no cover - non-fatal
            current_app.logger.info("Pickup notification email skipped: %s", e)

        flash(
            "Your pickup request has been received. Your order number is {}. "
            "We'll contact you shortly to confirm.".format(order_number),
            "success",
        )
        return redirect(url_for("public.request_pickup") + "?submitted=1&order=" + order_number)

    submitted = request.args.get("submitted") == "1"
    order_number = request.args.get("order", "")

    return render_template(
        "public/request_pickup.html",
        form=form,
        company_name=company_name,
        submitted=submitted,
        order_number=order_number,
    )
