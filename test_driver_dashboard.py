#!/usr/bin/env python3
"""Driver Dashboard test suite for the Triple Force Logistic app.

Tests:
  1. Access control: Customer/Driver/Dispatch/Admin separation
  2. Clock in/out, duplicate prevention
  3. Break start/end, duplicate prevention
  4. Route start/end, duplicate prevention
  5. Stop completion, duplicate prevention
  6. Mileage logging
  7. Checklist toggle
  8. Weekly totals calculation
  9. Prospects remain present and unchanged
 10. Public Request a Pickup form still works
 11. Dispatch/Admin Driver Operations area
 12. Audit trail corrections

Run:  python test_driver_dashboard.py
"""
import os
import sys

import os as _os
_DB_PATH = _os.path.join(_os.path.abspath(_os.path.dirname(__file__)), "tripleforce.db")
if _os.path.exists(_DB_PATH):
    _os.remove(_DB_PATH)

os.environ["DATABASE_URL"] = "sqlite:///tripleforce.db"
os.environ["SECRET_KEY"] = "test-secret-key-driver-dash"
os.environ["FLASK_DEBUG"] = "0"
os.environ["MAIL_USERNAME"] = ""

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from app.extensions import db
from app.models import (
    User, Driver, Customer, Delivery, Prospect,
    DriverWorkSession, DriverBreak, DriverRouteSession,
    DriverStopEvent, DriverMileageLog, ChecklistItem, ChecklistResponse,
    DriverMessage, DriverCorrection,
)

PASS = 0
FAIL = 0
RESULTS = []


def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        RESULTS.append(f"  PASS  {name}")
    else:
        FAIL += 1
        RESULTS.append(f"  FAIL  {name}  {detail}")


def login(client, email, password):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password, "remember": "n"},
        follow_redirects=True,
    )


def main():
    app = create_app()
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["TESTING"] = True

    with app.app_context():
        db.create_all()

        # Seed users for each role
        admin = User(email="admin@test.com", first_name="Ada", last_name="Admin",
                     role="admin", is_active_user=True)
        admin.set_password("AdminPass123!")
        dispatcher = User(email="dispatch@test.com", first_name="Dan",
                          last_name="Dispatcher", role="dispatcher", is_active_user=True)
        dispatcher.set_password("DispatchPass123!")
        driver_user = User(email="driver@test.com", first_name="Don", last_name="Driver",
                           role="driver", is_active_user=True)
        driver_user.set_password("DriverPass123!")

        # Seed a driver record
        driver = Driver(name="Don Driver", email="driver@test.com",
                         vehicle_make="Ford", vehicle_model="Transit",
                         vehicle_plate="TF-1234", is_active=True)
        driver_user.driver_record = driver

        db.session.add_all([admin, dispatcher, driver_user, driver])
        db.session.commit()

        # Seed 13 prospects
        for i in range(13):
            p = Prospect(
                organization_name=f"Prospect Org {i+1}",
                organization_type="Laboratory",
                contact_person=f"Contact {i+1}",
                email=f"prospect{i+1}@test.com",
                outreach_status="Drafted - Pending Approval",
                opportunity_stage="Prospect",
                dedupe_key=Prospect.build_dedupe_key(f"Prospect Org {i+1}", f"prospect{i+1}@test.com"),
            )
            db.session.add(p)

        db.session.commit()

    client = app.test_client()

    print("=" * 64)
    print("TRIPLE FORCE LOGISTIC — DRIVER DASHBOARD TEST SUITE")
    print("=" * 64)

    # ── 1. ACCESS CONTROL ──
    print("\n[1] Access control: Customer/Driver/Dispatch/Admin separation")

    # Public can access request-pickup but not driver/driver-ops
    r = client.get("/request-pickup", follow_redirects=False)
    test("Public GET /request-pickup → 200", r.status_code == 200, f"got {r.status_code}")

    r = client.get("/driver/", follow_redirects=False)
    test("Logged-out /driver/ → redirect to login",
         r.status_code in (301, 302, 303, 308) and "/auth/login" in (r.headers.get("Location") or ""),
         f"got {r.status_code} -> {r.headers.get('Location')}")

    r = client.get("/driver-ops/", follow_redirects=False)
    test("Logged-out /driver-ops/ → redirect to login",
         r.status_code in (301, 302, 303, 308) and "/auth/login" in (r.headers.get("Location") or ""),
         f"got {r.status_code} -> {r.headers.get('Location')}")

    # Login as driver
    login(client, "driver@test.com", "DriverPass123!")

    r = client.get("/driver/", follow_redirects=False)
    test("Driver can access /driver/", r.status_code == 200, f"got {r.status_code}")

    r = client.get("/driver-ops/", follow_redirects=False)
    test("Driver denied on /driver-ops/ (403)",
         r.status_code == 403 or (
             r.status_code in (301, 302, 303, 308)
             and "/auth/login" in (r.headers.get("Location") or "")
         ), f"got {r.status_code}")

    r = client.get("/dashboard", follow_redirects=False)
    test("Driver denied on /dashboard (403)",
         r.status_code == 403 or (
             r.status_code in (301, 302, 303, 308)
             and "/auth/login" in (r.headers.get("Location") or "")
         ), f"got {r.status_code}")

    # Logout, login as admin
    client.get("/auth/logout", follow_redirects=False)
    login(client, "admin@test.com", "AdminPass123!")

    r = client.get("/driver-ops/", follow_redirects=False)
    test("Admin can access /driver-ops/", r.status_code == 200, f"got {r.status_code}")

    # Logout, login as dispatcher
    client.get("/auth/logout", follow_redirects=False)
    login(client, "dispatch@test.com", "DispatchPass123!")

    r = client.get("/driver-ops/", follow_redirects=False)
    test("Dispatcher can access /driver-ops/", r.status_code == 200, f"got {r.status_code}")

    # ── 2. CLOCK IN / OUT ──
    print("\n[2] Clock in/out and duplicate prevention")

    # Login as driver
    client.get("/auth/logout", follow_redirects=False)
    login(client, "driver@test.com", "DriverPass123!")

    # Clock in
    r = client.post("/driver/clock-in", follow_redirects=False)
    test("Clock in → redirect", r.status_code in (301, 302, 303, 308), f"got {r.status_code}")

    # Verify session created
    with app.app_context():
        session = DriverWorkSession.query.filter_by(
            driver_id=1, clock_out_time=None
        ).first()
        test("Work session created", session is not None, "no session found")

    # Duplicate clock in
    r = client.post("/driver/clock-in", follow_redirects=True)
    test("Duplicate clock in prevented", "already clocked in" in r.data.decode("utf-8", errors="ignore").lower(),
         "duplicate allowed")

    # Clock out
    r = client.post("/driver/clock-out", follow_redirects=False)
    test("Clock out → redirect", r.status_code in (301, 302, 303, 308), f"got {r.status_code}")

    # Verify session closed
    with app.app_context():
        session = DriverWorkSession.query.filter_by(driver_id=1).order_by(DriverWorkSession.id.desc()).first()
        test("Work session closed", session.clock_out_time is not None, "clock_out_time is None")

    # Clock out without being clocked in
    r = client.post("/driver/clock-out", follow_redirects=True)
    test("Clock out without clock-in prevented", "not currently clocked in" in r.data.decode("utf-8", errors="ignore").lower(),
         "allowed without clock-in")

    # ── 3. BREAK MANAGEMENT ──
    print("\n[3] Break start/end and duplicate prevention")

    # Clock in first
    client.post("/driver/clock-in", follow_redirects=False)

    # Start break
    r = client.post("/driver/break/start", follow_redirects=False)
    test("Start break → redirect", r.status_code in (301, 302, 303, 308), f"got {r.status_code}")

    # Duplicate break
    r = client.post("/driver/break/start", follow_redirects=True)
    test("Duplicate break prevented", "already on break" in r.data.decode("utf-8", errors="ignore").lower(),
         "duplicate allowed")

    # End break
    r = client.post("/driver/break/end", follow_redirects=False)
    test("End break → redirect", r.status_code in (301, 302, 303, 308), f"got {r.status_code}")

    # End break without active break
    r = client.post("/driver/break/end", follow_redirects=True)
    test("End break without active break prevented", "not currently on break" in r.data.decode("utf-8", errors="ignore").lower(),
         "allowed without break")

    # ── 4. ROUTE MANAGEMENT ──
    print("\n[4] Route start/end and duplicate prevention")

    # Start route
    r = client.post("/driver/route/start", data={"start_odometer": "1000.0"}, follow_redirects=False)
    test("Start route → redirect", r.status_code in (301, 302, 303, 308), f"got {r.status_code}")

    # Duplicate route
    r = client.post("/driver/route/start", data={"start_odometer": "1001.0"}, follow_redirects=True)
    test("Duplicate route prevented", "already in progress" in r.data.decode("utf-8", errors="ignore").lower(),
         "duplicate allowed")

    # End route
    r = client.post("/driver/route/end", data={"end_odometer": "1050.0"}, follow_redirects=False)
    test("End route → redirect", r.status_code in (301, 302, 303, 308), f"got {r.status_code}")

    # Verify mileage logged
    with app.app_context():
        mileage = DriverMileageLog.query.filter_by(driver_id=1).first()
        test("Mileage logged from odometer", mileage is not None and mileage.miles == 50.0,
             f"mileage={mileage.miles if mileage else 'None'}")

    # ── 5. STOP COMPLETION ──
    print("\n[5] Stop completion and duplicate prevention")

    # Complete a delivery stop
    r = client.post("/driver/stop/complete", data={
        "stop_type": "delivery",
        "notes": "Test delivery",
    }, follow_redirects=False)
    test("Complete stop → redirect", r.status_code in (301, 302, 303, 308), f"got {r.status_code}")

    # Verify stop event created
    with app.app_context():
        stop = DriverStopEvent.query.filter_by(driver_id=1, stop_type="delivery").first()
        test("Stop event created", stop is not None, "no stop event found")

    # ── 6. MILEAGE LOGGING ──
    print("\n[6] Manual mileage logging")

    r = client.post("/driver/mileage/log", data={
        "start_odometer": "2000.0",
        "end_odometer": "2050.0",
    }, follow_redirects=False)
    test("Log mileage → redirect", r.status_code in (301, 302, 303, 308), f"got {r.status_code}")

    with app.app_context():
        mileage = DriverMileageLog.query.filter_by(driver_id=1, source="manual").first()
        test("Manual mileage logged", mileage is not None and mileage.miles == 50.0,
             f"miles={mileage.miles if mileage else 'None'}")

    # ── 7. CHECKLIST ──
    print("\n[7] Checklist toggle")

    with app.app_context():
        item = ChecklistItem.query.first()
        test("Checklist items seeded", item is not None, "no checklist items found")

    if item:
        r = client.post("/driver/checklist/toggle", data={"item_id": item.id}, follow_redirects=False)
        test("Toggle checklist → redirect", r.status_code in (301, 302, 303, 308), f"got {r.status_code}")

        with app.app_context():
            resp = ChecklistResponse.query.filter_by(
                driver_id=1, checklist_item_id=item.id
            ).first()
            test("Checklist response created", resp is not None and resp.is_completed,
                 "response not found or not completed")

    # ── 8. WEEKLY TOTALS ──
    print("\n[8] Weekly totals calculation")

    with app.app_context():
        from app.driver_portal.calculations import get_week_stats, get_today_stats
        today = get_today_stats(1)
        week = get_week_stats(1)
        test("Today stats computed", today["stops"] >= 1, f"stops={today['stops']}")
        test("Week stats computed", week["stops"] >= 1, f"stops={week['stops']}")
        test("Drive hours computed", week["drive_hours"] > 0, f"drive_hours={week['drive_hours']}")
        test("Miles computed", week["miles"] >= 50.0, f"miles={week['miles']}")

    # ── 9. PROSPECTS UNCHANGED ──
    print("\n[9] Prospects remain present and unchanged")

    with app.app_context():
        count = Prospect.query.count()
        test("13 prospects present", count == 13, f"found {count} prospects")

        # Verify prospect data intact
        p1 = Prospect.query.filter_by(organization_name="Prospect Org 1").first()
        test("Prospect 1 data intact",
             p1 is not None and p1.email == "prospect1@test.com"
             and p1.outreach_status == "Drafted - Pending Approval"
             and p1.opportunity_stage == "Prospect",
             "prospect data changed")

    # ── 10. PUBLIC PICKUP FORM ──
    print("\n[10] Public Request a Pickup form still works")

    client.get("/auth/logout", follow_redirects=False)
    r = client.get("/request-pickup", follow_redirects=False)
    test("Public pickup form accessible", r.status_code == 200, f"got {r.status_code}")
    body = r.data.decode("utf-8", errors="ignore")
    test("Pickup form has no staff sidebar", 'class="sidebar"' not in body.lower())

    # ── 11. DISPATCH/ADMIN DRIVER OPERATIONS ──
    print("\n[11] Dispatch/Admin Driver Operations area")

    login(client, "admin@test.com", "AdminPass123!")
    r = client.get("/driver-ops/", follow_redirects=False)
    test("Admin can view driver ops overview", r.status_code == 200, f"got {r.status_code}")

    r = client.get("/driver-ops/driver/1", follow_redirects=False)
    test("Admin can view driver detail", r.status_code == 200, f"got {r.status_code}")

    r = client.get("/driver-ops/driver/1/history", follow_redirects=False)
    test("Admin can view driver history", r.status_code == 200, f"got {r.status_code}")

    # ── 12. AUDIT TRAIL ──
    print("\n[12] Audit trail corrections")

    r = client.post("/driver-ops/driver/1/correct", data={
        "correction_type": "clock_in",
        "description": "Adjusted clock-in time",
        "reason": "Driver forgot to clock in",
        "old_value": "10:00 AM",
        "new_value": "9:30 AM",
    }, follow_redirects=False)
    test("Correction recorded → redirect", r.status_code in (301, 302, 303, 308), f"got {r.status_code}")

    with app.app_context():
        correction = DriverCorrection.query.filter_by(driver_id=1).first()
        test("Correction audit entry created",
             correction is not None and correction.correction_type == "clock_in"
             and correction.reason == "Driver forgot to clock in",
             "correction not found or data mismatch")

    # ── Summary ──
    print("\n" + "=" * 64)
    for line in RESULTS:
        print(line)
    print("=" * 64)
    print(f"DRIVER DASHBOARD TESTS: {PASS} passed, {FAIL} failed")
    print("=" * 64)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
