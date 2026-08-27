"""Driver Operations routes — protected dispatch/admin area for monitoring all drivers.

Access: admin or dispatcher role only.  Drivers cannot access these routes.
"""
from datetime import datetime, date, timedelta

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models import (
    Driver, Delivery, DriverWorkSession, DriverBreak, DriverRouteSession,
    DriverStopEvent, DriverMileageLog, ChecklistItem, ChecklistResponse,
    DriverMessage, DriverCorrection, DriverWeeklySummary,
)
from app.driver_portal.calculations import (
    get_active_work_session, get_active_break, get_active_route_session,
    get_driver_status_label, get_today_stats, get_week_stats,
    get_42_week_history, get_recent_messages,
)
from app.utils import dispatcher_or_above

driver_ops = Blueprint("driver_ops", __name__)


def _resolve_driver_id(driver_id):
    """Resolve a driver ID, ensuring dispatch/admin can access any driver."""
    driver = db.session.get(Driver, driver_id)
    if not driver:
        abort(404)
    return driver


@driver_ops.route("/")
@login_required
@dispatcher_or_above
def overview():
    """Driver Operations overview — who is clocked in, active routes, metrics."""
    drivers = Driver.query.filter_by(is_active=True).order_by(Driver.name).all()
    driver_data = []
    for d in drivers:
        session = get_active_work_session(d.id)
        route = get_active_route_session(d.id)
        today_stats = get_today_stats(d.id)
        status = get_driver_status_label(d.id)

        # Next stop = first incomplete delivery assigned to this driver
        next_delivery = Delivery.query.filter(
            Delivery.driver_id == d.id,
            Delivery.status.notin_(["Delivered", "Completed", "Cancelled"]),
        ).order_by(Delivery.pickup_datetime.asc()).first()

        driver_data.append({
            "driver": d,
            "status": status,
            "session": session,
            "route": route,
            "today": today_stats,
            "next_delivery": next_delivery,
        })

    return render_template("driver_ops/overview.html", driver_data=driver_data)


@driver_ops.route("/driver/<int:driver_id>")
@login_required
@dispatcher_or_above
def driver_detail(driver_id):
    """Detailed view of a single driver's current activity."""
    driver = _resolve_driver_id(driver_id)
    session = get_active_work_session(driver.id)
    route = get_active_route_session(driver.id)
    today_stats = get_today_stats(driver.id)
    week_stats = get_week_stats(driver.id)
    status = get_driver_status_label(driver.id)

    # Recent stops
    recent_stops = DriverStopEvent.query.filter_by(
        driver_id=driver.id
    ).order_by(DriverStopEvent.completed_at.desc()).limit(20).all()

    # Checklist completion
    today = date.today()
    checklist_items = ChecklistItem.query.filter_by(is_active=True).order_by(ChecklistItem.sort_order).all()
    checklist_responses = {}
    for item in checklist_items:
        resp = ChecklistResponse.query.filter_by(
            driver_id=driver.id,
            checklist_item_id=item.id,
            response_date=today,
        ).first()
        checklist_responses[item.id] = resp

    # Recent messages
    messages = get_recent_messages(driver.id, limit=20)

    # Assigned deliveries
    assigned = Delivery.query.filter(
        Delivery.driver_id == driver.id,
        Delivery.status.notin_(["Delivered", "Completed", "Cancelled"]),
    ).order_by(Delivery.pickup_datetime.asc()).all()

    # Unassigned deliveries (for assign form)
    unassigned_deliveries = Delivery.query.filter(
        Delivery.driver_id.is_(None),
        Delivery.status.notin_(["Delivered", "Completed", "Cancelled"]),
    ).order_by(Delivery.created_at.desc()).limit(50).all()

    return render_template(
        "driver_ops/detail.html",
        driver=driver,
        status=status,
        session=session,
        route=route,
        today_stats=today_stats,
        week_stats=week_stats,
        recent_stops=recent_stops,
        checklist_items=checklist_items,
        checklist_responses=checklist_responses,
        messages=messages,
        assigned=assigned,
        unassigned_deliveries=unassigned_deliveries,
    )


@driver_ops.route("/driver/<int:driver_id>/history")
@login_required
@dispatcher_or_above
def driver_history(driver_id):
    """View 42-week history for a driver."""
    driver = _resolve_driver_id(driver_id)
    history = get_42_week_history(driver.id)
    return render_template("driver_ops/history.html", driver=driver, history=history)


@driver_ops.route("/driver/<int:driver_id>/message", methods=["POST"])
@login_required
@dispatcher_or_above
def send_message(driver_id):
    """Send a message to a driver."""
    driver = _resolve_driver_id(driver_id)
    message_text = request.form.get("message", "").strip()
    priority = request.form.get("priority", "normal")

    if not message_text:
        flash("Message cannot be empty.", "danger")
        return redirect(url_for("driver_ops.driver_detail", driver_id=driver.id))

    msg = DriverMessage(
        driver_id=driver.id,
        sender_id=current_user.id,
        message=message_text,
        priority=priority,
    )
    db.session.add(msg)
    db.session.commit()

    flash(f"Message sent to {driver.name}.", "success")
    return redirect(url_for("driver_ops.driver_detail", driver_id=driver.id))


@driver_ops.route("/driver/<int:driver_id>/assign", methods=["POST"])
@login_required
@dispatcher_or_above
def assign_route(driver_id):
    """Assign or reassign a delivery to a driver."""
    driver = _resolve_driver_id(driver_id)
    delivery_id = request.form.get("delivery_id")

    if not delivery_id:
        flash("No delivery selected.", "danger")
        return redirect(url_for("driver_ops.driver_detail", driver_id=driver.id))

    delivery = db.session.get(Delivery, delivery_id)
    if not delivery:
        flash("Delivery not found.", "danger")
        return redirect(url_for("driver_ops.driver_detail", driver_id=driver.id))

    old_driver = delivery.driver.name if delivery.driver else "Unassigned"
    delivery.driver_id = driver.id
    if delivery.status == "New Request":
        delivery.status = "Driver Assigned"
    delivery.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f"Delivery {delivery.order_number} assigned to {driver.name}.", "success")
    return redirect(url_for("driver_ops.driver_detail", driver_id=driver.id))


@driver_ops.route("/driver/<int:driver_id>/correct", methods=["POST"])
@login_required
@dispatcher_or_above
def correct_entry(driver_id):
    """Correct a driver entry with full audit trail."""
    driver = _resolve_driver_id(driver_id)
    correction_type = request.form.get("correction_type", "")
    description = request.form.get("description", "").strip()
    reason = request.form.get("reason", "").strip()
    old_value = request.form.get("old_value", "").strip()
    new_value = request.form.get("new_value", "").strip()

    if not correction_type or not description or not reason:
        flash("Correction type, description, and reason are required.", "danger")
        return redirect(url_for("driver_ops.driver_detail", driver_id=driver.id))

    correction = DriverCorrection(
        driver_id=driver.id,
        corrected_by=current_user.id,
        correction_type=correction_type,
        description=description,
        reason=reason,
        old_value=old_value or None,
        new_value=new_value or None,
    )
    db.session.add(correction)
    db.session.commit()

    flash("Correction recorded in audit trail.", "success")
    return redirect(url_for("driver_ops.driver_detail", driver_id=driver.id))


@driver_ops.route("/driver/<int:driver_id>/audit")
@login_required
@dispatcher_or_above
def audit_trail(driver_id):
    """View the full audit trail for a driver."""
    driver = _resolve_driver_id(driver_id)
    corrections = DriverCorrection.query.filter_by(
        driver_id=driver.id
    ).order_by(DriverCorrection.created_at.desc()).limit(100).all()
    return render_template("driver_ops/audit_trail.html", driver=driver, corrections=corrections)
