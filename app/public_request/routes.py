"""Public customer-facing routes (no login required, no internal navigation).

These routes are intentionally separate from the staff `main`/`dispatch`
blueprints so they never inherit the internal sidebar or admin navigation,
regardless of whether a staff member happens to be logged in.
"""
from datetime import datetime
import secrets
from threading import Thread

from flask import (
    Blueprint, render_template, request, flash, redirect, url_for, current_app,
    session,
)
from app.extensions import db
from app.models import Delivery, DeliveryStatusHistory
from app.forms import CustomerPickupRequestForm
from app.utils import get_next_order_number, get_company_settings
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

public = Blueprint("public", __name__)


def _send_pickup_notification(app, recipient, subject, body):
    """Send the non-critical notification outside the customer request."""
    with app.app_context():
        try:
            from app.utils import send_email
            send_email(recipient, subject, body)
        except Exception as exc:  # pragma: no cover - defensive worker guard
            app.logger.info("Pickup notification email skipped: %s", exc)


@public.route("/")
def home():
    """Public branded gateway at the site root.

    This is the single entry point for web traffic. It is NOT the staff
    dashboard and is NOT the pickup form — it links to both. No login
    required, no sidebar, no internal navigation.
    """
    settings = get_company_settings()
    company_name = settings.company_name if settings else "Triple Force Logistic LLC"
    return render_template("public/home.html", company_name=company_name)


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
    submission_token = session.get("pickup_submission_token")
    if request.method == "GET" and not submission_token:
        submission_token = secrets.token_urlsafe(32)
        session["pickup_submission_token"] = submission_token
    if request.method == "GET":
        form.submission_token.data = submission_token
    settings = get_company_settings()
    company_name = settings.company_name if settings else "Triple Force Logistic LLC"

    if form.validate_on_submit():
        if form.submission_token.data != submission_token:
            existing = Delivery.query.filter_by(
                public_submission_token=form.submission_token.data
            ).first()
            if existing:
                return redirect(
                    url_for("public.request_pickup")
                    + "?submitted=1&order=" + existing.order_number
                )
            form.submission_token.errors.append("This pickup form has expired. Please reload and try again.")
            return render_template(
                "public/request_pickup.html", form=form, company_name=company_name,
                submitted=False, order_number="",
            ), 400
        order_number = get_next_order_number()

        pickup_date = (form.pickup_date.data or "").strip()
        pickup_time = (form.pickup_time.data or "").strip()
        try:
            pickup_datetime = datetime.strptime(f"{pickup_date} {pickup_time}", "%Y-%m-%d %H:%M")
        except ValueError:
            form.pickup_date.errors.append("Enter a valid pickup date and time.")
            return render_template(
                "public/request_pickup.html", form=form, company_name=company_name,
                submitted=False, order_number="",
            ), 400

        # Build a structured "requested by" block so dispatch can see who
        # placed the request even though there is no logged-in user.
        requested_by = "Requested by: {} | Phone: {}".format(
            form.requester_name.data, form.requester_phone.data
        )
        if form.requester_email.data:
            requested_by += " | Email: {}".format(form.requester_email.data)
        if form.company_facility_name.data:
            requested_by = "Company / Facility: {}\n".format(form.company_facility_name.data) + requested_by

        existing_notes = (form.customer_notes.data or "").strip()
        customer_notes = requested_by + ("\n\n" + existing_notes if existing_notes else "")

        # Fall back to the requester when no separate pickup/delivery contact
        # was provided, so the record always has a contactable person.
        requester_contact = "{} — {}".format(
            form.requester_name.data, form.requester_phone.data
        )

        delivery = Delivery(
            order_number=order_number,
            public_submission_token=submission_token,
            customer_id=None,  # public submission — not linked to a Customer record
            company_facility_name=form.company_facility_name.data or None,
            pickup_contact=form.pickup_contact.data or requester_contact,
            pickup_contact_phone=form.pickup_contact_phone.data or None,
            pickup_address=form.pickup_address.data,
            pickup_instructions=form.pickup_instructions.data,
            pickup_datetime=pickup_datetime,
            delivery_contact=form.delivery_contact.data or form.requester_name.data,
            delivery_contact_phone=form.delivery_contact_phone.data or None,
            delivery_address=form.delivery_address.data,
            delivery_instructions=form.delivery_instructions.data,
            delivery_deadline=form.requested_delivery_deadline.data,
            service_type=form.service_type.data,
            delivery_type=form.delivery_type.data or None,
            delivery_type_other=(form.delivery_type_other.data or None) if form.delivery_type.data == "Other" else None,
            trip_type=form.trip_type.data or None,
            package_type=form.package_type.data,
            quantity=form.quantity.data or 1,
            package_weight=form.package_weight.data or None,
            package_size=form.package_size.data or None,
            special_handling=form.special_handling.data,
            reference_number=form.reference_number.data or None,
            is_medical=form.is_medical.data,
            pickup_facility=form.pickup_facility.data,
            delivery_facility=form.delivery_facility.data,
            temperature_requirement=form.temperature_requirement.data or None,
            is_recurring=(form.is_recurring.data == "Yes"),
            recurring_route_notes=(form.recurring_route_notes.data or None) if form.is_recurring.data == "Yes" else None,
            customer_notes=customer_notes,
            created_by=None,  # no logged-in staff user for public submissions
            status="New Request",
        )
        db.session.add(delivery)

        # Mirror the staff route: create the initial status-history entry so
        # the dispatch timeline is consistent for public submissions too.
        history = DeliveryStatusHistory(
            delivery=delivery,
            status="New Request",
            notes="Pickup request submitted from public website",
            updated_by=form.requester_name.data or "Website customer",
        )
        db.session.add(history)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            existing = Delivery.query.filter_by(public_submission_token=submission_token).first()
            if existing:
                session.pop("pickup_submission_token", None)
                return redirect(
                    url_for("public.request_pickup")
                    + "?submitted=1&order=" + existing.order_number
                )
            current_app.logger.exception("Public pickup request could not be saved")
            flash(
                "We could not save your pickup request. Please try again. "
                "If the problem continues, contact us directly.",
                "error",
            )
            return render_template(
                "public/request_pickup.html", form=form, company_name=company_name,
                submitted=False, order_number="",
            ), 500
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Public pickup request could not be saved")
            flash(
                "We could not save your pickup request. Please try again. "
                "If the problem continues, contact us directly.",
                "error",
            )
            return render_template(
                "public/request_pickup.html", form=form, company_name=company_name,
                submitted=False, order_number="",
            ), 500

        session.pop("pickup_submission_token", None)

        # Best-effort internal notification email. It runs after persistence in
        # a short-lived background thread so SMTP cannot delay confirmation.
        try:
            notify_to = settings.email if settings else current_app.config.get("MAIL_DEFAULT_SENDER")
            if notify_to:
                body = (
                    "A new pickup request was submitted from the website.\n\n"
                    "Order #: {}\n"
                    "Company / Facility: {}\n"
                    "Requested by: {}\n"
                    "Phone: {}\n"
                    "Pickup: {}\n"
                    "Delivery: {}\n"
                    "Service: {} | Delivery Type: {} | Trip: {}\n"
                    "Recurring: {}\n".format(
                        order_number,
                        form.company_facility_name.data or "—",
                        form.requester_name.data,
                        form.requester_phone.data,
                        form.pickup_address.data,
                        form.delivery_address.data,
                        form.service_type.data,
                        form.delivery_type.data or "—",
                        form.trip_type.data or "—",
                        "Yes" if form.is_recurring.data == "Yes" else "No",
                    )
                )
                notification_thread = Thread(
                    target=_send_pickup_notification,
                    args=(
                        current_app._get_current_object(),
                        notify_to,
                        "New Pickup Request — {}".format(order_number),
                        body,
                    ),
                    daemon=True,
                )
                notification_thread.start()
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
