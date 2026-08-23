"""Local test for the public /request-pickup route.

Verifies:
  - GET /request-pickup returns 200 and renders the customer form
  - the public page contains NO internal sidebar / staff nav labels
  - POST with valid data creates a Delivery (status 'New Request') and
    shows a confirmation with the order number
  - internal routes (/dashboard, /, /customers/, /dispatch/) redirect to
    login when logged out (still protected)
"""
import os
import tempfile

# Use a clean temp SQLite DB so we don't touch the committed tripleforce.db
os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.mktemp(suffix=".db")
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FLASK_DEBUG"] = "0"
os.environ["MAIL_USERNAME"] = ""  # no SMTP in tests -> send_email logs & returns False

import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from app.extensions import db
from app.models import Delivery

# Internal sidebar labels that must NEVER appear on the public page
INTERNAL_LABELS = [
    "Outreach Tracker", "Quote Calculator", "Dispatch", "Invoices",
    "Revenue", "Reminders", "Settings", "User Management",
]
# Sidebar markup markers that must be absent on the public page
SIDEBAR_MARKERS = ['class="sidebar"', 'id="sidebar"', 'sidebar-link', 'sidebar-toggle', 'sidebar-nav']


def main():
    app = create_app()
    # Disable CSRF for the test client so we can POST without a token
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["TESTING"] = True

    failures = []

    with app.app_context():
        db.create_all()

    client = app.test_client()

    # ── 1. GET /request-pickup (logged out) ──
    r = client.get("/request-pickup")
    print(f"[GET /request-pickup] status={r.status_code}")
    if r.status_code != 200:
        failures.append(f"GET /request-pickup returned {r.status_code}, expected 200")
    body = r.get_data(as_text=True)

    if "Request a Pickup" not in body:
        failures.append("GET page does not contain the 'Request a Pickup' heading")
    if 'name="requester_name"' not in body:
        failures.append("GET page missing requester_name field")
    if 'name="pickup_address"' not in body:
        failures.append("GET page missing pickup_address field")
    if 'name="delivery_address"' not in body:
        failures.append("GET page missing delivery_address field")
    if "Request Pickup" not in body:
        failures.append("GET page missing submit button")

    # ── 2. No internal nav / sidebar on the public page ──
    found_labels = [lbl for lbl in INTERNAL_LABELS if lbl in body]
    found_markers = [m for m in SIDEBAR_MARKERS if m in body]
    if found_labels:
        failures.append(f"Internal nav labels found on public page: {found_labels}")
    if found_markers:
        failures.append(f"Sidebar markup found on public page: {found_markers}")
    # The public page should not link to any staff route
    staff_routes = ["/dashboard", "/customers", "/dispatch", "/invoices", "/quotes", "/reports"]
    found_routes = [rt for rt in staff_routes if f'href="{rt}' in body or f'href="/{rt}"' in body]
    if found_routes:
        failures.append(f"Staff route links found on public page: {found_routes}")

    # ── 3. POST valid pickup request ──
    payload = {
        "requester_name": "Jane Customer",
        "requester_phone": "(555) 222-3333",
        "requester_email": "jane@example.com",
        "pickup_contact": "Front Desk",
        "pickup_address": "123 Main St, New York, NY 10001",
        "pickup_instructions": "Loading dock B",
        "pickup_datetime": "2026-08-24T09:00",
        "delivery_contact": "Dr. Smith",
        "delivery_address": "456 Health Ave, New York, NY 10002",
        "delivery_instructions": "Lab window",
        "service_type": "STAT",
        "package_type": "Medical Box",
        "quantity": "2",
        "special_handling": "Refrigerated, fragile",
        "is_medical": "y",
        "pickup_facility": "NYC Lab",
        "delivery_facility": "Smith Clinic",
        "temperature_requirement": "Refrigerated",
        "customer_notes": "Call on arrival",
    }
    r = client.post("/request-pickup", data=payload, follow_redirects=True)
    print(f"[POST /request-pickup] status={r.status_code}")
    body = r.get_data(as_text=True)
    if r.status_code != 200:
        failures.append(f"POST returned {r.status_code}, expected 200 (after redirect)")
    if "Pickup Request Received" not in body:
        failures.append("POST response missing 'Pickup Request Received' confirmation")
    if "TF-" not in body:
        failures.append("POST response missing generated order number (TF-xxxx)")
    if "123 Main St" in body and "Request a Pickup</h1>" in body and "Pickup Request Received" not in body:
        failures.append("Form appears not to have been accepted (still showing blank form)")

    # Verify the Delivery was created in the DB
    with app.app_context():
        deliveries = Delivery.query.order_by(Delivery.id.desc()).all()
        created = deliveries[0] if deliveries else None
        if not created:
            failures.append("No Delivery record was created by POST")
        else:
            print(f"[DB] Created Delivery id={created.id} order={created.order_number} "
                  f"status={created.status} is_medical={created.is_medical} "
                  f"service_type={created.service_type} created_by={created.created_by}")
            if created.status != "New Request":
                failures.append(f"Delivery status={created.status}, expected 'New Request'")
            if created.created_by is not None:
                failures.append(f"Delivery.created_by={created.created_by}, expected None (public)")
            if "Jane Customer" not in (created.customer_notes or ""):
                failures.append("customer_notes does not record the requester name")
            if created.pickup_address != "123 Main St, New York, NY 10001":
                failures.append("pickup_address not persisted correctly")
            if created.is_medical is not True:
                failures.append("is_medical not persisted correctly")
            # Status history should mirror the staff route for timeline consistency
            hist = created.status_history or []
            print(f"[DB] status_history rows={len(hist)} first={hist[0].status if hist else None} "
                  f"notes={ (hist[0].notes if hist else None)!r}")
            if not hist:
                failures.append("No DeliveryStatusHistory row created for public submission")
            elif hist[0].status != "New Request":
                failures.append(f"status_history[0].status={hist[0].status}, expected 'New Request'")
            elif "public website" not in (hist[0].notes or ""):
                failures.append("status_history notes does not mention public website")

    # ── 4. Root "/" is the public gateway (landing page), and staff routes
    #    require login when logged out. ──
    r = client.get("/")
    body_root = r.get_data(as_text=True)
    print(f"[GET /] status={r.status_code}")
    if r.status_code != 200:
        failures.append(f"/ should return 200 landing page; got {r.status_code}")
    if "Request a Pickup" not in body_root:
        failures.append("Landing page missing 'Request a Pickup' button")
    if "/request-pickup" not in body_root:
        failures.append("Landing page missing link to /request-pickup")
    if "/auth/login" not in body_root:
        failures.append("Landing page missing Staff Login link to /auth/login")
    if "sidebar-link" in body_root or 'class="sidebar"' in body_root:
        failures.append("Landing page exposed sidebar/internal nav")
    for path in ["/dashboard", "/customers/", "/dispatch/", "/invoices/", "/quotes/", "/reports/"]:
        r = client.get(path)
        loc = r.headers.get("Location", "")
        ok = r.status_code in (301, 302) and "/auth/login" in loc
        print(f"[GET {path}] status={r.status_code} -> {loc}  protected={ok}")
        if not ok:
            failures.append(f"{path} not protected: status={r.status_code} loc={loc}")

    # ── 5. Sanity: a logged-in staff user visiting /request-pickup ALSO sees no sidebar ──
    # (Simulate by creating a user and logging in via the test client.)
    from app.models import User
    with app.app_context():
        u = User(email="staff@test.local", role="admin",
                 password_hash="x", first_name="Staff", last_name="User", is_active_user=True)
        db.session.add(u)
        db.session.commit()
        uid = u.id
    # Log in
    client.post("/auth/login", data={"email": "staff@test.local", "password": "irrelevant-hash-check"},
                follow_redirects=False)
    # NOTE: real login checks password hash; this may not authenticate. Instead, force
    # a logged-in session by using the test client's session directly.
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)
        sess["_fresh"] = True
    r = client.get("/request-pickup")
    body = r.get_data(as_text=True)
    found_markers = [m for m in SIDEBAR_MARKERS if m in body]
    print(f"[GET /request-pickup as logged-in staff] status={r.status_code} sidebar_markers={found_markers}")
    if found_markers:
        failures.append(f"Logged-in staff still sees sidebar on public page: {found_markers}")

    print("\n" + "=" * 60)
    if failures:
        print(f"FAILURES ({len(failures)}):")
        for f in failures:
            print("  - " + f)
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
