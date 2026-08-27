"""Driver dashboard calculation helpers.

All calculations are based on server-side timestamps so they do not depend
on the phone screen remaining open.  Durations are computed from stored
clock-in/out, break, and route-session records.

Workweek: Monday 00:00 ET – Sunday 23:59 ET (America/New_York).
"""
from datetime import datetime, date, timedelta
from sqlalchemy import func

from app.extensions import db
from app.models import (
    Driver, DriverWorkSession, DriverBreak, DriverRouteSession,
    DriverStopEvent, DriverMileageLog, ChecklistItem, ChecklistResponse,
    DriverMessage, DriverWeeklySummary,
)


# ── Workweek helpers ──
def get_week_start(target_date=None):
    """Return the Monday of the week containing target_date."""
    if target_date is None:
        target_date = date.today()
    return target_date - timedelta(days=target_date.weekday())


def get_week_end(target_date=None):
    """Return the Sunday of the week containing target_date."""
    return get_week_start(target_date) + timedelta(days=6)


def get_week_start_for_weeks_ago(weeks_ago):
    """Return the Monday of the week N weeks ago."""
    return get_week_start() - timedelta(weeks=weeks_ago)


# ── Active session helpers ──
def get_active_work_session(driver_id):
    """Return the driver's currently open work session, or None."""
    return DriverWorkSession.query.filter_by(
        driver_id=driver_id, clock_out_time=None
    ).order_by(DriverWorkSession.clock_in_time.desc()).first()


def get_active_break(driver_id):
    """Return the driver's currently open break, or None."""
    return DriverBreak.query.filter_by(
        driver_id=driver_id, end_time=None
    ).order_by(DriverBreak.start_time.desc()).first()


def get_active_route_session(driver_id):
    """Return the driver's currently open route session, or None."""
    return DriverRouteSession.query.filter_by(
        driver_id=driver_id, end_time=None
    ).order_by(DriverRouteSession.start_time.desc()).first()


# ── Duration calculations ──
def calculate_work_hours(sessions, start_dt=None, end_dt=None):
    """Calculate total work hours from a list of work sessions.

    Work hours = clock-in to clock-out, minus break time.
    If clock_out_time is None (still working), use now() as the end.
    """
    now = datetime.utcnow()
    total_seconds = 0
    for s in sessions:
        start = max(s.clock_in_time, start_dt) if start_dt else s.clock_in_time
        end = s.clock_out_time or now
        if end_dt:
            end = min(end, end_dt)
        if start >= end:
            continue
        gross = (end - start).total_seconds()
        # Subtract break time within this session
        for b in s.breaks:
            b_start = b.start_time
            b_end = b.end_time or now
            # Clamp break to the session window
            b_start = max(b_start, start)
            b_end = min(b_end, end)
            if b_start < b_end:
                gross -= (b_end - b_start).total_seconds()
        total_seconds += max(0, gross)
    return total_seconds / 3600.0


def calculate_drive_hours(route_sessions, start_dt=None, end_dt=None):
    """Calculate total driving hours from route sessions.

    Drive hours = route start to route end, minus break time during route.
    """
    now = datetime.utcnow()
    total_seconds = 0
    for rs in route_sessions:
        start = max(rs.start_time, start_dt) if start_dt else rs.start_time
        end = rs.end_time or now
        if end_dt:
            end = min(end, end_dt)
        if start >= end:
            continue
        gross = (end - start).total_seconds()
        # Subtract breaks that fall within this route session
        ws = rs.work_session
        if ws:
            for b in ws.breaks:
                b_start = b.start_time
                b_end = b.end_time or now
                b_start = max(b_start, start)
                b_end = min(b_end, end)
                if b_start < b_end:
                    gross -= (b_end - b_start).total_seconds()
        total_seconds += max(0, gross)
    return total_seconds / 3600.0


def calculate_miles(driver_id, start_date=None, end_date=None):
    """Calculate total miles from mileage logs within a date range."""
    query = db.session.query(func.sum(DriverMileageLog.miles)).filter(
        DriverMileageLog.driver_id == driver_id
    )
    if start_date:
        query = query.filter(DriverMileageLog.log_date >= start_date)
    if end_date:
        query = query.filter(DriverMileageLog.log_date <= end_date)
    result = query.scalar()
    return float(result or 0)


def count_stops(driver_id, start_dt=None, end_dt=None):
    """Count completed stops within a time range."""
    query = DriverStopEvent.query.filter(DriverStopEvent.driver_id == driver_id)
    if start_dt:
        query = query.filter(DriverStopEvent.completed_at >= start_dt)
    if end_dt:
        query = query.filter(DriverStopEvent.completed_at <= end_dt)
    return query.count()


def count_by_type(driver_id, stop_type, start_dt=None, end_dt=None):
    """Count stops of a specific type (delivery, pickup) within a time range."""
    query = DriverStopEvent.query.filter(
        DriverStopEvent.driver_id == driver_id,
        DriverStopEvent.stop_type == stop_type,
    )
    if start_dt:
        query = query.filter(DriverStopEvent.completed_at >= start_dt)
    if end_dt:
        query = query.filter(DriverStopEvent.completed_at <= end_dt)
    return query.count()


def calculate_stops_per_hour(stops, drive_hours):
    """Calculate stops per hour with zero-hour guard."""
    if not drive_hours or drive_hours <= 0:
        return 0.0
    return round(stops / drive_hours, 2)


# ── Today and week stats ──
def get_today_stats(driver_id):
    """Return all stats for today."""
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today + timedelta(days=1), datetime.min.time())

    sessions = DriverWorkSession.query.filter(
        DriverWorkSession.driver_id == driver_id,
        DriverWorkSession.clock_in_time < today_end,
        db.or_(
            DriverWorkSession.clock_out_time.is_(None),
            DriverWorkSession.clock_out_time >= today_start,
        ),
    ).all()

    route_sessions = DriverRouteSession.query.filter(
        DriverRouteSession.driver_id == driver_id,
        DriverRouteSession.start_time < today_end,
        db.or_(
            DriverRouteSession.end_time.is_(None),
            DriverRouteSession.end_time >= today_start,
        ),
    ).all()

    work_hours = calculate_work_hours(sessions, today_start, today_end)
    drive_hours = calculate_drive_hours(route_sessions, today_start, today_end)
    miles = calculate_miles(driver_id, today, today)
    stops = count_stops(driver_id, today_start, today_end)
    deliveries = count_by_type(driver_id, "delivery", today_start, today_end)
    pickups = count_by_type(driver_id, "pickup", today_start, today_end)

    return {
        "work_hours": work_hours,
        "drive_hours": drive_hours,
        "miles": miles,
        "stops": stops,
        "deliveries": deliveries,
        "pickups": pickups,
        "stops_per_hour": calculate_stops_per_hour(stops, drive_hours),
    }


def get_week_stats(driver_id, weeks_ago=0):
    """Return all stats for the current week (or N weeks ago)."""
    week_start = get_week_start_for_weeks_ago(weeks_ago)
    week_end = get_week_end(week_start)
    week_start_dt = datetime.combine(week_start, datetime.min.time())
    week_end_dt = datetime.combine(week_end + timedelta(days=1), datetime.min.time())

    sessions = DriverWorkSession.query.filter(
        DriverWorkSession.driver_id == driver_id,
        DriverWorkSession.clock_in_time < week_end_dt,
        db.or_(
            DriverWorkSession.clock_out_time.is_(None),
            DriverWorkSession.clock_out_time >= week_start_dt,
        ),
    ).all()

    route_sessions = DriverRouteSession.query.filter(
        DriverRouteSession.driver_id == driver_id,
        DriverRouteSession.start_time < week_end_dt,
        db.or_(
            DriverRouteSession.end_time.is_(None),
            DriverRouteSession.end_time >= week_start_dt,
        ),
    ).all()

    work_hours = calculate_work_hours(sessions, week_start_dt, week_end_dt)
    drive_hours = calculate_drive_hours(route_sessions, week_start_dt, week_end_dt)
    miles = calculate_miles(driver_id, week_start, week_end)
    stops = count_stops(driver_id, week_start_dt, week_end_dt)
    deliveries = count_by_type(driver_id, "delivery", week_start_dt, week_end_dt)
    pickups = count_by_type(driver_id, "pickup", week_start_dt, week_end_dt)

    return {
        "work_hours": work_hours,
        "drive_hours": drive_hours,
        "miles": miles,
        "stops": stops,
        "deliveries": deliveries,
        "pickups": pickups,
        "stops_per_hour": calculate_stops_per_hour(stops, drive_hours),
        "week_start": week_start,
        "week_end": week_end,
    }


def get_42_week_history(driver_id):
    """Return weekly summaries for the last 42 weeks."""
    summaries = []
    for i in range(42):
        stats = get_week_stats(driver_id, weeks_ago=i)
        summaries.append({
            "week_start": stats["week_start"],
            "week_end": stats["week_end"],
            "work_hours": round(stats["work_hours"], 2),
            "drive_hours": round(stats["drive_hours"], 2),
            "miles": round(stats["miles"], 2),
            "stops": stats["stops"],
            "deliveries": stats["deliveries"],
            "pickups": stats["pickups"],
            "stops_per_hour": stats["stops_per_hour"],
        })
    return summaries


# ── Checklist helpers ──
def get_active_checklist_items():
    """Return all active checklist items ordered by sort_order."""
    return ChecklistItem.query.filter_by(is_active=True).order_by(ChecklistItem.sort_order).all()


def get_today_checklist(driver_id):
    """Return today's checklist responses for a driver."""
    today = date.today()
    items = get_active_checklist_items()
    responses = {}
    for item in items:
        resp = ChecklistResponse.query.filter_by(
            driver_id=driver_id,
            checklist_item_id=item.id,
            response_date=today,
        ).first()
        responses[item.id] = resp
    return items, responses


def get_checklist_completion_count(driver_id):
    """Return (completed_count, total_count) for today's checklist."""
    items, responses = get_today_checklist(driver_id)
    completed = sum(1 for item in items if responses.get(item.id) and responses[item.id].is_completed)
    return completed, len(items)


# ── Message helpers ──
def get_unread_messages(driver_id):
    """Return unread messages for a driver."""
    return DriverMessage.query.filter_by(
        driver_id=driver_id, is_read=False
    ).order_by(DriverMessage.created_at.desc()).all()


def get_recent_messages(driver_id, limit=10):
    """Return recent messages for a driver."""
    return DriverMessage.query.filter_by(
        driver_id=driver_id
    ).order_by(DriverMessage.created_at.desc()).limit(limit).all()


# ── Driver status label ──
def get_driver_status_label(driver_id):
    """Return a human-readable status for the driver."""
    session = get_active_work_session(driver_id)
    if not session:
        return "Off Duty"

    if session.status == "off_duty":
        return "Off Duty"

    active_break = get_active_break(driver_id)
    if active_break:
        return "On Break"

    if session.status == "on_route":
        return "On Route"

    if session.status == "route_completed":
        return "Route Completed"

    return "Clocked In"
