"""Driver Portal routes — driver-facing views scoped to their own assigned deliveries.

Access: driver, dispatcher, or admin role.  Drivers see only their own data.
All timestamps are stored server-side — calculations do not depend on the
phone screen remaining open.
"""
from datetime import datetime, date

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import (
    Delivery, DeliveryStatusHistory, ProofOfDelivery, ChainOfCustody,
    Driver, DELIVERY_STATUSES,
    DriverWorkSession, DriverBreak, DriverRouteSession,
    DriverStopEvent, DriverMileageLog,
    ChecklistItem, ChecklistResponse, DriverMessage,
)
from app.forms import DeliveryStatusUpdateForm, DriverPODForm, ChainOfCustodyForm
from app.utils import driver_or_above, send_email, get_company_settings
from app.driver_portal.calculations import (
    get_active_work_session, get_active_break, get_active_route_session,
    get_driver_status_label, get_today_stats, get_week_stats,
    get_today_checklist, get_checklist_completion_count,
    get_unread_messages, get_recent_messages,
)

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


# ═══════════════════════════════════════════════════════════════
#  ENHANCED DRIVER DASHBOARD
# ═══════════════════════════════════════════════════════════════
@driver_portal.route("/")
@login_required
@driver_or_above
def dashboard():
    """Driver dashboard — mobile-first, branded, with full metrics and controls."""
    driver = _get_current_driver()
    if not driver:
        flash("No driver profile is linked to your account. Contact your administrator.", "warning")
        return render_template("driver_portal/dashboard.html", driver=None)

    # Active session state
    session = get_active_work_session(driver.id)
    active_break = get_active_break(driver.id)
    active_route = get_active_route_session(driver.id)
    status = get_driver_status_label(driver.id)

    # Stats
    today_stats = get_today_stats(driver.id)
    week_stats = get_week_stats(driver.id)

    # Checklist
    checklist_items, checklist_responses = get_today_checklist(driver.id)
    checklist_completed, checklist_total = get_checklist_completion_count(driver.id)

    # Messages
    unread_messages = get_unread_messages(driver.id)
    recent_messages = get_recent_messages(driver.id, limit=5)

    # Assigned deliveries (next stops)
    today = date.today()
    assigned = Delivery.query.filter(
        Delivery.driver_id == driver.id,
        Delivery.status.notin_(["Delivered", "Completed", "Cancelled"]),
    ).order_by(Delivery.pickup_datetime.asc()).all()

    next_stop = assigned[0] if assigned else None

    # Has routing API configured? (for Optimize button)
    has_routing_api = bool(get_company_settings() and
                          get_company_settings().email)

    return render_template(
        "driver_portal/dashboard.html",
        driver=driver,
        status=status,
        session=session,
        active_break=active_break,
        active_route=active_route,
        today_stats=today_stats,
        week_stats=week_stats,
        checklist_items=checklist_items,
        checklist_responses=checklist_responses,
        checklist_completed=checklist_completed,
        checklist_total=checklist_total,
        unread_messages=unread_messages,
        recent_messages=recent_messages,
        assigned=assigned,
        next_stop=next_stop,
        has_routing_api=has_routing_api,
    )


# ═══════════════════════════════════════════════════════════════
#  CLOCK IN / CLOCK OUT
# ═══════════════════════════════════════════════════════════════
@driver_portal.route("/clock-in", methods=["POST"])
@login_required
@driver_or_above
def clock_in():
    """Start a work session. Prevents duplicate clock-ins."""
    driver = _get_current_driver()
    if not driver:
        flash("No driver profile linked to your account.", "danger")
        return redirect(url_for("driver_portal.dashboard"))

    existing = get_active_work_session(driver.id)
    if existing:
        flash("You are already clocked in.", "warning")
        return redirect(url_for("driver_portal.dashboard"))

    session = DriverWorkSession(
        driver_id=driver.id,
        user_id=current_user.id,
        clock_in_time=datetime.utcnow(),
        status="clocked_in",
    )
    db.session.add(session)
    db.session.commit()
    flash("Clocked in successfully.", "success")
    return redirect(url_for("driver_portal.dashboard"))


@driver_portal.route("/clock-out", methods=["POST"])
@login_required
@driver_or_above
def clock_out():
    """End the work session. Prevents clocking out when not clocked in."""
    driver = _get_current_driver()
    if not driver:
        flash("No driver profile linked to your account.", "danger")
        return redirect(url_for("driver_portal.dashboard"))

    session = get_active_work_session(driver.id)
    if not session:
        flash("You are not currently clocked in.", "warning")
        return redirect(url_for("driver_portal.dashboard"))

    # End any active break first
    active_break = get_active_break(driver.id)
    if active_break:
        active_break.end_time = datetime.utcnow()

    # End any active route first
    active_route = get_active_route_session(driver.id)
    if active_route:
        active_route.end_time = datetime.utcnow()

    session.clock_out_time = datetime.utcnow()
    session.status = "off_duty"
    db.session.commit()
    flash("Clocked out. Work session ended.", "success")
    return redirect(url_for("driver_portal.dashboard"))


# ═══════════════════════════════════════════════════════════════
#  BREAK MANAGEMENT
# ═══════════════════════════════════════════════════════════════
@driver_portal.route("/break/start", methods=["POST"])
@login_required
@driver_or_above
def start_break():
    """Start a break. Prevents duplicate breaks."""
    driver = _get_current_driver()
    if not driver:
        flash("No driver profile linked to your account.", "danger")
        return redirect(url_for("driver_portal.dashboard"))

    session = get_active_work_session(driver.id)
    if not session:
        flash("You must clock in before taking a break.", "warning")
        return redirect(url_for("driver_portal.dashboard"))

    existing_break = get_active_break(driver.id)
    if existing_break:
        flash("You are already on break.", "warning")
        return redirect(url_for("driver_portal.dashboard"))

    break_record = DriverBreak(
        work_session_id=session.id,
        driver_id=driver.id,
        start_time=datetime.utcnow(),
    )
    db.session.add(break_record)

    # Save previous status and set to on_break
    session.status = session.status  # preserve for resume
    session.status = "on_break"
    db.session.commit()
    flash("Break started.", "success")
    return redirect(url_for("driver_portal.dashboard"))


@driver_portal.route("/break/end", methods=["POST"])
@login_required
@driver_or_above
def end_break():
    """End the current break."""
    driver = _get_current_driver()
    if not driver:
        flash("No driver profile linked to your account.", "danger")
        return redirect(url_for("driver_portal.dashboard"))

    active_break = get_active_break(driver.id)
    if not active_break:
        flash("You are not currently on break.", "warning")
        return redirect(url_for("driver_portal.dashboard"))

    active_break.end_time = datetime.utcnow()

    # Restore status: if there's an active route, go back to on_route, else clocked_in
    session = get_active_work_session(driver.id)
    if session:
        active_route = get_active_route_session(driver.id)
        if active_route:
            session.status = "on_route"
        else:
            session.status = "clocked_in"

    db.session.commit()
    flash("Break ended.", "success")
    return redirect(url_for("driver_portal.dashboard"))


# ═══════════════════════════════════════════════════════════════
#  ROUTE MANAGEMENT
# ═══════════════════════════════════════════════════════════════
@driver_portal.route("/route/start", methods=["POST"])
@login_required
@driver_or_above
def start_route():
    """Start a route session. Prevents duplicate routes."""
    driver = _get_current_driver()
    if not driver:
        flash("No driver profile linked to your account.", "danger")
        return redirect(url_for("driver_portal.dashboard"))

    session = get_active_work_session(driver.id)
    if not session:
        flash("You must clock in before starting a route.", "warning")
        return redirect(url_for("driver_portal.dashboard"))

    existing_route = get_active_route_session(driver.id)
    if existing_route:
        flash("A route is already in progress.", "warning")
        return redirect(url_for("driver_portal.dashboard"))

    start_odometer = request.form.get("start_odometer")
    start_odo_val = float(start_odometer) if start_odometer else None

    route = DriverRouteSession(
        work_session_id=session.id,
        driver_id=driver.id,
        start_time=datetime.utcnow(),
        start_odometer=start_odo_val,
    )
    db.session.add(route)
    session.status = "on_route"
    db.session.commit()
    flash("Route started.", "success")
    return redirect(url_for("driver_portal.dashboard"))


@driver_portal.route("/route/end", methods=["POST"])
@login_required
@driver_or_above
def end_route():
    """End the current route session."""
    driver = _get_current_driver()
    if not driver:
        flash("No driver profile linked to your account.", "danger")
        return redirect(url_for("driver_portal.dashboard"))

    active_route = get_active_route_session(driver.id)
    if not active_route:
        flash("No active route to end.", "warning")
        return redirect(url_for("driver_portal.dashboard"))

    end_odometer = request.form.get("end_odometer")
    end_odo_val = float(end_odometer) if end_odometer else None

    active_route.end_time = datetime.utcnow()
    active_route.end_odometer = end_odo_val

    # Log mileage if both odometer readings exist
    if active_route.start_odometer and end_odo_val:
        miles = end_odo_val - active_route.start_odometer
        if miles > 0:
            mileage_log = DriverMileageLog(
                driver_id=driver.id,
                route_session_id=active_route.id,
                log_date=date.today(),
                start_odometer=active_route.start_odometer,
                end_odometer=end_odo_val,
                miles=round(miles, 2),
                source="odometer",
            )
            db.session.add(mileage_log)

    # Update session status
    session = get_active_work_session(driver.id)
    if session:
        session.status = "route_completed"

    db.session.commit()
    flash("Route ended.", "success")
    return redirect(url_for("driver_portal.dashboard"))


# ═══════════════════════════════════════════════════════════════
#  STOP / PACKAGE EVENTS
# ═══════════════════════════════════════════════════════════════
@driver_portal.route("/stop/complete", methods=["POST"])
@login_required
@driver_or_above
def complete_stop():
    """Mark a stop as completed. Prevents duplicate stop completions."""
    driver = _get_current_driver()
    if not driver:
        flash("No driver profile linked to your account.", "danger")
        return redirect(url_for("driver_portal.dashboard"))

    session = get_active_work_session(driver.id)
    if not session:
        flash("You must clock in before completing stops.", "warning")
        return redirect(url_for("driver_portal.dashboard"))

    stop_type = request.form.get("stop_type", "other")
    delivery_id = request.form.get("delivery_id")
    notes = request.form.get("notes", "").strip()

    # Check for duplicate stop completion (same delivery + same work session)
    if delivery_id:
        existing = DriverStopEvent.query.filter_by(
            driver_id=driver.id,
            work_session_id=session.id,
            delivery_id=int(delivery_id),
            stop_type=stop_type,
        ).first()
        if existing:
            flash("This stop has already been completed.", "warning")
            return redirect(url_for("driver_portal.dashboard"))

    route = get_active_route_session(driver.id)

    stop_event = DriverStopEvent(
        driver_id=driver.id,
        work_session_id=session.id,
        route_session_id=route.id if route else None,
        delivery_id=int(delivery_id) if delivery_id else None,
        stop_type=stop_type,
        completed_at=datetime.utcnow(),
        notes=notes or None,
    )
    db.session.add(stop_event)

    # If linked to a delivery, update its status
    if delivery_id:
        delivery = db.session.get(Delivery, int(delivery_id))
        if delivery and delivery.driver_id == driver.id:
            if stop_type == "delivery":
                delivery.status = "Delivered"
                if not delivery.actual_delivery_time:
                    delivery.actual_delivery_time = datetime.utcnow()
            elif stop_type == "pickup":
                delivery.status = "Picked Up"
                if not delivery.actual_pickup_time:
                    delivery.actual_pickup_time = datetime.utcnow()
            delivery.updated_at = datetime.utcnow()
            history = DeliveryStatusHistory(
                delivery_id=delivery.id,
                status=delivery.status,
                notes=f"Stop completed by {current_user.full_name or current_user.email}",
                updated_by=current_user.full_name or current_user.email,
            )
            db.session.add(history)

    db.session.commit()
    flash(f"Stop completed: {stop_type}.", "success")
    return redirect(url_for("driver_portal.dashboard"))


@driver_portal.route("/mileage/log", methods=["POST"])
@login_required
@driver_or_above
def log_mileage():
    """Log a manual mileage entry."""
    driver = _get_current_driver()
    if not driver:
        flash("No driver profile linked to your account.", "danger")
        return redirect(url_for("driver_portal.dashboard"))

    start_odo = request.form.get("start_odometer")
    end_odo = request.form.get("end_odometer")
    log_date_str = request.form.get("log_date", str(date.today()))

    if not start_odo or not end_odo:
        flash("Both odometer readings are required.", "danger")
        return redirect(url_for("driver_portal.dashboard"))

    try:
        start_val = float(start_odo)
        end_val = float(end_odo)
        if end_val <= start_val:
            flash("End odometer must be greater than start.", "danger")
            return redirect(url_for("driver_portal.dashboard"))
        miles = round(end_val - start_val, 2)
    except ValueError:
        flash("Invalid odometer values.", "danger")
        return redirect(url_for("driver_portal.dashboard"))

    route = get_active_route_session(driver.id)
    log = DriverMileageLog(
        driver_id=driver.id,
        route_session_id=route.id if route else None,
        log_date=date.fromisoformat(log_date_str) if log_date_str else date.today(),
        start_odometer=start_val,
        end_odometer=end_val,
        miles=miles,
        source="manual",
    )
    db.session.add(log)
    db.session.commit()
    flash(f"Mileage logged: {miles} miles.", "success")
    return redirect(url_for("driver_portal.dashboard"))


# ═══════════════════════════════════════════════════════════════
#  CHECKLIST
# ═══════════════════════════════════════════════════════════════
@driver_portal.route("/checklist/toggle", methods=["POST"])
@login_required
@driver_or_above
def toggle_checklist_item():
    """Toggle a checklist item completion status."""
    driver = _get_current_driver()
    if not driver:
        flash("No driver profile linked to your account.", "danger")
        return redirect(url_for("driver_portal.dashboard"))

    item_id = request.form.get("item_id")
    if not item_id:
        flash("No checklist item specified.", "danger")
        return redirect(url_for("driver_portal.dashboard"))

    item = db.session.get(ChecklistItem, int(item_id))
    if not item:
        flash("Checklist item not found.", "danger")
        return redirect(url_for("driver_portal.dashboard"))

    today = date.today()
    resp = ChecklistResponse.query.filter_by(
        driver_id=driver.id,
        checklist_item_id=item.id,
        response_date=today,
    ).first()

    if resp:
        resp.is_completed = not resp.is_completed
        resp.completed_at = datetime.utcnow() if resp.is_completed else None
    else:
        resp = ChecklistResponse(
            driver_id=driver.id,
            user_id=current_user.id,
            checklist_item_id=item.id,
            response_date=today,
            is_completed=True,
            completed_at=datetime.utcnow(),
        )
        db.session.add(resp)

    db.session.commit()
    flash(f"Checklist updated: {item.label}.", "success")
    return redirect(url_for("driver_portal.dashboard"))


# ═══════════════════════════════════════════════════════════════
#  MESSAGES
# ═══════════════════════════════════════════════════════════════
@driver_portal.route("/messages")
@login_required
@driver_or_above
def messages():
    """View all messages for the driver."""
    driver = _get_current_driver()
    if not driver:
        flash("No driver profile linked to your account.", "danger")
        return redirect(url_for("driver_portal.dashboard"))

    all_messages = get_recent_messages(driver.id, limit=50)
    return render_template("driver_portal/messages.html", driver=driver, messages=all_messages)


@driver_portal.route("/messages/<int:message_id>/read", methods=["POST"])
@login_required
@driver_or_above
def mark_message_read(message_id):
    """Mark a message as read."""
    msg = db.session.get(DriverMessage, message_id)
    if not msg:
        abort(404)

    driver = _get_current_driver()
    if not driver or msg.driver_id != driver.id:
        abort(403)

    msg.is_read = True
    db.session.commit()
    flash("Message marked as read.", "success")
    return redirect(url_for("driver_portal.messages"))


# ═══════════════════════════════════════════════════════════════
#  EXISTING ROUTES (preserved unchanged)
# ═══════════════════════════════════════════════════════════════
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
