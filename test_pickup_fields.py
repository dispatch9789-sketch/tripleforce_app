"""Tests for the expanded public /request-pickup form.

Verifies:
  - GET /request-pickup renders all the new fields, including Rush in the
    Service Type dropdown and the Delivery Type / Trip Type dropdowns.
  - POST with a full payload (including Rush, "Other" delivery type with a
    description, recurring route with notes) persists EVERY new field to the
    Delivery record.
  - A logged-in dispatcher/admin viewing /dispatch/<id> sees every new value
    rendered on the staff request-detail page (requirement 15).
  - Public page still exposes no internal nav/sidebar/staff routes (security
    separation preserved — requirements 14/16).
  - Staff-only routes still redirect to login when logged out.
"""
import os
import sys
import tempfile

# Isolated temp DB (do NOT touch the committed tripleforce.db)
_TMP_DB = "sqlite:///" + tempfile.mktemp(suffix=".db")
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FLASK_DEBUG"] = "0"
os.environ["MAIL_USERNAME"] = ""  # no SMTP in tests

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Delivery, User


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = _TMP_DB
    WTF_CSRF_ENABLED = False
    TESTING = True


INTERNAL_LABELS = [
    "Outreach Tracker", "Quote Calculator", "Dispatch", "Invoices",
    "Revenue", "Reminders", "Settings", "User Management",
]
SIDEBAR_MARKERS = ['class="sidebar"', 'id="sidebar"', 'sidebar-link', 'sidebar-toggle', 'sidebar-nav']


def main():
    app = create_app(config_class=TestConfig)
    client = app.test_client()
    failures = []

    with app.app_context():
        db.create_all()
        # A dispatcher role user to view the staff detail page
        u = User(email="dispatch@test.local", role="dispatcher",
                 password_hash="x", first_name="Disp", last_name="User", is_active_user=True)
        db.session.add(u)
        db.session.commit()
        uid = u.id

    # ── 1. GET the form and check every new field is present ──
    r = client.get("/request-pickup")
    body = r.get_data(as_text=True)
    print(f"[GET /request-pickup] status={r.status_code}")
    if r.status_code != 200:
        failures.append(f"GET returned {r.status_code}, expected 200")
    expected_fields = [
        "company_facility_name", "pickup_contact_phone", "delivery_contact_phone",
        "delivery_type", "delivery_type_other", "trip_type", "package_weight",
        "package_size", "reference_number", "is_recurring", "recurring_route_notes",
        "requested_delivery_deadline", "temperature_requirement",
    ]
    for f in expected_fields:
        if f'name="{f}"' not in body:
            failures.append(f"form missing input name={f}")
    # Rush must appear as a Service Type option
    if 'value="Rush"' not in body:
        failures.append("Service Type dropdown missing 'Rush' option")
    # Delivery Type options
    for opt in ["Medical Specimen / Lab Sample", "Pharmacy / Medication",
                "Medical Supplies / Equipment", "Documents / Records",
                "General Package", "Auto Parts", "Other"]:
        if opt not in body:
            failures.append(f"Delivery Type missing option: {opt}")
    # Trip Type options
    for opt in ["One-way", "Round Trip", "Multi-stop"]:
        if opt not in body:
            failures.append(f"Trip Type missing option: {opt}")
    # Temperature dropdown options
    for opt in ["Room Temperature", "Refrigerated", "Frozen", "Other / Special Requirement"]:
        if opt not in body:
            failures.append(f"Temperature Requirement missing option: {opt}")

    # ── 2. No internal nav on the public page ──
    found_labels = [lbl for lbl in INTERNAL_LABELS if lbl in body]
    found_markers = [m for m in SIDEBAR_MARKERS if m in body]
    if found_labels:
        failures.append(f"Internal nav labels on public page: {found_labels}")
    if found_markers:
        failures.append(f"Sidebar markup on public page: {found_markers}")

    # ── 3. POST a full payload exercising every new field ──
    payload = {
        "company_facility_name": "Riverside Imaging Center",
        "requester_name": "Jane Customer",
        "requester_phone": "(555) 222-3333",
        "requester_email": "jane@example.com",
        "pickup_contact": "Front Desk",
        "pickup_contact_phone": "(555) 222-4444",
        "pickup_address": "123 Main St, New York, NY 10001",
        "pickup_instructions": "Loading dock B, call upon arrival",
        "pickup_datetime": "2026-08-24T09:00",
        "delivery_contact": "Dr. Smith",
        "delivery_contact_phone": "(555) 222-5555",
        "delivery_address": "456 Health Ave, New York, NY 10002",
        "delivery_instructions": "Lab window 2, ring bell",
        "requested_delivery_deadline": "2026-08-24T11:30",
        "service_type": "Rush",
        "delivery_type": "Other",
        "delivery_type_other": "Biological samples in cooler",
        "trip_type": "Round Trip",
        "package_type": "Medical Box",
        "quantity": "2",
        "package_weight": "5 lbs",
        "package_size": "12x8x6 in",
        "special_handling": "Refrigerated, fragile",
        "reference_number": "PO-8842 / ACME",
        "is_medical": "y",
        "pickup_facility": "NYC Lab",
        "delivery_facility": "Smith Clinic",
        "temperature_requirement": "Refrigerated",
        "is_recurring": "Yes",
        "recurring_route_notes": "Mon/Wed/Fri 9am pickup",
        "customer_notes": "Call on arrival",
    }
    r = client.post("/request-pickup", data=payload, follow_redirects=True)
    body = r.get_data(as_text=True)
    print(f"[POST /request-pickup] status={r.status_code}")
    if r.status_code != 200:
        failures.append(f"POST returned {r.status_code}, expected 200")
    if "Pickup Request Received" not in body:
        failures.append("POST response missing confirmation")

    # ── 4. Verify every new field persisted to the Delivery record ──
    with app.app_context():
        created = Delivery.query.order_by(Delivery.id.desc()).first()
        if not created:
            failures.append("No Delivery record created")
        else:
            checks = {
                "company_facility_name": created.company_facility_name,
                "pickup_contact_phone": created.pickup_contact_phone,
                "delivery_contact_phone": created.delivery_contact_phone,
                "delivery_type": created.delivery_type,
                "delivery_type_other": created.delivery_type_other,
                "trip_type": created.trip_type,
                "package_weight": created.package_weight,
                "package_size": created.package_size,
                "reference_number": created.reference_number,
                "temperature_requirement": created.temperature_requirement,
                "recurring_route_notes": created.recurring_route_notes,
            }
            for k, v in checks.items():
                if not v:
                    failures.append(f"field {k} not persisted (got {v!r})")
            if created.service_type != "Rush":
                failures.append(f"service_type={created.service_type}, expected 'Rush'")
            if created.is_recurring is not True:
                failures.append(f"is_recurring={created.is_recurring}, expected True")
            if created.delivery_deadline is None:
                failures.append("requested_delivery_deadline (delivery_deadline) not persisted")
            delivery_id = created.id

    # ── 5. Staff request-detail page renders every new value ──
    if not failures:
        with client.session_transaction() as sess:
            sess["_user_id"] = str(uid)
            sess["_fresh"] = True
        r = client.get(f"/dispatch/{delivery_id}")
        dbody = r.get_data(as_text=True)
        print(f"[GET /dispatch/{delivery_id}] status={r.status_code}")
        if r.status_code != 200:
            failures.append(f"dispatch detail returned {r.status_code}, expected 200")
        else:
            detail_checks = [
                "Riverside Imaging Center", "(555) 222-4444", "(555) 222-5555",
                "Biological samples in cooler", "Round Trip", "5 lbs", "12x8x6 in",
                "PO-8842 / ACME", "Refrigerated", "Mon/Wed/Fri 9am pickup",
            ]
            for needle in detail_checks:
                if needle not in dbody:
                    failures.append(f"dispatch detail missing value: {needle!r}")
            # No internal sidebar should be injected into the public page, but
            # the staff detail page legitimately has one — make sure it is the
            # STAFF page (has 'Chain of Custody') not the public one.
            if "Chain of Custody" not in dbody:
                failures.append("dispatch detail missing Chain of Custody section")

    # ── 6. Staff-only routes still redirect to login when logged out ──
    client.get("/auth/logout", follow_redirects=False)  # clear session just in case
    for path in ["/dashboard", "/dispatch/", "/invoices/", "/quotes/", "/reports/"]:
        r = client.get(path)
        loc = r.headers.get("Location", "")
        ok = r.status_code in (301, 302) and "/auth/login" in loc
        print(f"[GET {path}] status={r.status_code} protected={ok}")
        if not ok:
            failures.append(f"{path} not protected: {r.status_code} -> {loc}")

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
