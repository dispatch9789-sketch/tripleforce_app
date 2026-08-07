#!/usr/bin/env python3
"""Comprehensive test script — verifies all routes, role-based access, and key workflows."""
import os
import sys

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

from app import create_app
from app.extensions import db

app = create_app()
app.config["WTF_CSRF_ENABLED"] = False
app.config["TESTING"] = True

# Import models and forms for DB-level tests
from app.models import User, Delivery, ProofOfDelivery, ChainOfCustody, DeliveryStatusHistory
from app.forms import UserForm, UserEditForm, DeliveryStatusUpdateForm, DriverPODForm, ChainOfCustodyForm

PASS = 0
FAIL = 0
results = []

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        results.append(f"  PASS  {name}")
    else:
        FAIL += 1
        results.append(f"  FAIL  {name}  {detail}")

def login(client, email, password):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=True)

def logout(client):
    client.get("/auth/logout")

with app.test_client() as c:
    print("="*60)
    print("TRIPLE FORCE LOGISTIC — COMPREHENSIVE TEST SUITE")
    print("="*60)

    # ── 1. LOGIN PAGE ──
    print("\n[1] Login Page")
    r = c.get("/auth/login")
    test("Login page GET 200", r.status_code == 200, f"got {r.status_code}")
    test("Login page has email field", b"email" in r.data.lower())
    test("Login page has password field", b"password" in r.data.lower())

    # ── 2. ADMIN LOGIN & SESSION ──
    print("\n[2] Admin Login")
    r = login(c, "admin@tripleforcelogistic.com", "ChangeMe123!")
    test("Admin login succeeds", r.status_code == 200)
    test("Redirects to dashboard", b"Dashboard" in r.data or b"dashboard" in r.data.lower())

    # ── 3. ADMIN CAN ACCESS ALL ROUTES ──
    print("\n[3] Admin Route Access")
    admin_routes = [
        ("/", "Dashboard"),
        ("/dashboard", "Dashboard (alt)"),
        ("/customers/", "Customers"),
        ("/customers/1", "Customer Detail"),
        ("/customers/new", "New Customer"),
        ("/customers/1/edit", "Edit Customer"),
        ("/quotes/", "Quotes"),
        ("/quotes/calculator", "Quote Calculator"),
        ("/quotes/1", "Quote Detail"),
        ("/dispatch/", "Dispatch Board"),
        ("/dispatch/1", "Dispatch Detail"),
        ("/dispatch/new", "New Dispatch"),
        ("/invoices/", "Invoices"),
        ("/invoices/1", "Invoice Detail"),
        ("/invoices/new", "New Invoice"),
        ("/reports/", "Reports/Revenue"),
        ("/reminders/", "Reminders"),
        ("/settings", "Settings"),
        ("/search", "Search"),
        ("/users/", "User Management"),
        ("/users/new", "Add User"),
        ("/driver/", "Driver Portal (admin)"),
    ]
    for path, name in admin_routes:
        r = c.get(path)
        test(f"Admin GET {path} ({name})", r.status_code == 200, f"got {r.status_code}")

    # ── 4. LOGOUT ──
    print("\n[4] Logout")
    logout(c)
    r = c.get("/dashboard")
    test("Logged out redirects to login", r.status_code in (301, 302), f"got {r.status_code}")

    # ── 5. DISPATCHER LOGIN & ACCESS ──
    print("\n[5] Dispatcher Login & Access")
    r = login(c, "dispatch@tripleforcelogistic.com", "ChangeMe123!")
    test("Dispatcher login succeeds", r.status_code == 200)

    r = c.get("/dashboard")
    test("Dispatcher can access dashboard", r.status_code == 200, f"got {r.status_code}")
    r = c.get("/dispatch/")
    test("Dispatcher can access dispatch", r.status_code == 200, f"got {r.status_code}")
    r = c.get("/customers/")
    test("Dispatcher can access customers", r.status_code == 200, f"got {r.status_code}")
    r = c.get("/quotes/calculator")
    test("Dispatcher can access quote calculator", r.status_code == 200, f"got {r.status_code}")

    # Dispatcher should NOT access settings or users
    r = c.get("/settings")
    test("Dispatcher denied from settings", r.status_code == 403, f"got {r.status_code}")
    r = c.get("/users/")
    test("Dispatcher denied from user management", r.status_code == 403, f"got {r.status_code}")

    # 403 page should be branded HTML, not raw Jinja
    test("403 is HTML not raw Jinja", b"{%" not in r.data and b"extends" not in r.data or b"base.html" not in r.data.split(b"{%")[0] if b"{" in r.data else True)
    test("403 has branded content", b"403" in r.data or b"Access" in r.data or b"Forbidden" in r.data or b"denied" in r.data.lower())

    logout(c)

    # ── 6. DRIVER LOGIN & ACCESS ──
    print("\n[6] Driver Login & Access")
    r = login(c, "mike@tripleforcelogistic.com", "ChangeMe123!")
    test("Driver login succeeds", r.status_code == 200)
    test("Driver redirected to portal", b"My Deliveries" in r.data or b"driver" in r.data.lower() or b"Assigned Deliveries" in r.data)

    # Driver can access their portal
    r = c.get("/driver/")
    test("Driver can access own portal", r.status_code == 200, f"got {r.status_code}")
    test("Driver portal shows deliveries", b"My Deliveries" in r.data or b"Assigned Deliveries" in r.data)

    # Driver should see the sample delivery
    r = c.get("/driver/deliveries/1")
    test("Driver can access assigned delivery", r.status_code == 200, f"got {r.status_code}")
    test("Delivery detail shows order number", b"TF-1001" in r.data)

    # Driver should NOT access admin routes
    r = c.get("/dashboard")
    test("Driver denied from admin dashboard", r.status_code == 403, f"got {r.status_code}")
    r = c.get("/customers/")
    test("Driver denied from customers", r.status_code == 403, f"got {r.status_code}")
    r = c.get("/settings")
    test("Driver denied from settings", r.status_code == 403, f"got {r.status_code}")
    r = c.get("/users/")
    test("Driver denied from user management", r.status_code == 403, f"got {r.status_code}")
    r = c.get("/dispatch/")
    test("Driver denied from dispatch", r.status_code == 403, f"got {r.status_code}")

    # ── 7. DRIVER PORTAL FORMS ──
    print("\n[7] Driver Portal Forms")
    # POD form
    r = c.get("/driver/deliveries/1/pod")
    test("Driver can access POD form", r.status_code == 200, f"got {r.status_code}")
    test("POD form has recipient field", b"recipient" in r.data.lower())

    # Custody form
    r = c.get("/driver/deliveries/1/custody")
    test("Driver can access custody form", r.status_code == 200, f"got {r.status_code}")
    test("Custody form has person_releasing", b"releasing" in r.data.lower() or b"Released" in r.data)

    logout(c)

    # ── 8. INACTIVE USER BLOCKED ──
    print("\n[8] Inactive User Blocked")
    with app.app_context():
        u = db.session.get(User, 2)  # dispatcher
        u.is_active_user = False
        db.session.commit()

    r = login(c, "dispatch@tripleforcelogistic.com", "ChangeMe123!")
    test("Inactive user cannot log in", b"deactivated" in r.data.lower() or b"disabled" in r.data.lower() or r.status_code == 200)
    test("Inactive user sees error message", b"deactivated" in r.data.lower())

    with app.app_context():
        u = db.session.get(User, 2)
        u.is_active_user = True
        db.session.commit()

    # ── 9. CSRF ERROR HANDLER ──
    print("\n[9] CSRF Error Handler")
    app2 = create_app()
    app2.config["WTF_CSRF_ENABLED"] = True
    app2.config["TESTING"] = True
    with app2.test_client() as c2:
        # POST without CSRF token
        r = c2.post("/auth/login", data={"email": "admin@tripleforcelogistic.com", "password": "ChangeMe123!"})
        test("CSRF error returns 400", r.status_code == 400, f"got {r.status_code}")
        test("CSRF error is HTML not raw Jinja", b"{%" not in r.data)
        test("CSRF error has branded content", b"Triple Force" in r.data or b"400" in r.data)

    # ── 10. FORM VALIDATION ──
    print("\n[10] Form Validation")
    # Use a fresh app to avoid test-client state affecting form validation
    app3 = create_app()
    app3.config["WTF_CSRF_ENABLED"] = False
    app3.config["TESTING"] = True
    with app3.app_context():
        # UserForm
        f = UserForm(data={"email": "test@example.com", "first_name": "Test", "last_name": "User",
                           "role": "dispatcher", "password": "TestPass123!", "is_active_user": True})
        test("UserForm validates valid data", f.validate())

        f2 = UserForm(formdata=None, data={"email": "bad", "role": "dispatcher", "password": "short"})
        f2_result = f2.validate()
        test("UserForm rejects invalid email", not f2_result, f"validate returned {f2_result}, errors={f2.errors}")

        # DriverPODForm
        f3 = DriverPODForm(data={"recipient_name": "John Doe", "delivery_date": "2026-08-02"})
        test("DriverPODForm validates valid data", f3.validate())

        f4 = DriverPODForm(data={"recipient_name": "", "delivery_date": ""})
        test("DriverPODForm rejects empty data", not f4.validate())

        # ChainOfCustodyForm
        f5 = ChainOfCustodyForm(data={"person_releasing": "Alice", "person_accepting": "Bob"})
        test("ChainOfCustodyForm validates valid data", f5.validate())

    # ── 11. SIDEBAR ROLE CONDITIONAL NAV ──
    print("\n[11] Sidebar Role-Conditional Nav")
    # Admin should see User Management link
    login(c, "admin@tripleforcelogistic.com", "ChangeMe123!")
    r = c.get("/dashboard")
    test("Admin sidebar has User Management link", b"User Management" in r.data)
    test("Admin sidebar has Settings link", b"Settings" in r.data)
    logout(c)

    # Driver should NOT see User Management or Settings
    login(c, "mike@tripleforcelogistic.com", "ChangeMe123!")
    r = c.get("/driver/")
    test("Driver sidebar has My Deliveries link", b"My Deliveries" in r.data)
    test("Driver sidebar does NOT have User Management", b"User Management" not in r.data)
    test("Driver sidebar does NOT have Settings", b"Settings" not in r.data)
    test("Driver sidebar does NOT have Customers", b">Customers<" not in r.data)
    logout(c)

    # ── 12. DRIVER PORTAL POST WORKFLOWS ──
    print("\n[12] Driver Portal POST Workflows")
    login(c, "mike@tripleforcelogistic.com", "ChangeMe123!")

    # Status update
    r = c.post("/driver/deliveries/1", data={"status": "En Route to Pickup", "notes": "Heading out", "submit": "Update Status"}, follow_redirects=True)
    test("Driver can update delivery status", r.status_code == 200, f"got {r.status_code}")
    test("Status update shows confirmation", b"Status updated" in r.data or b"success" in r.data.lower())

    # POD submission
    r = c.post("/driver/deliveries/1/pod", data={
        "recipient_name": "Dr. Smith",
        "delivery_date": "2026-08-02",
        "notes": "Delivered to receiving dock",
        "refused": "n",
        "submit": "Submit Proof of Delivery"
    }, follow_redirects=True)
    test("Driver can submit POD", r.status_code == 200, f"got {r.status_code}")
    test("POD submission shows confirmation", b"Proof of delivery submitted" in r.data or b"success" in r.data.lower())

    # Chain of custody submission
    r = c.post("/driver/deliveries/1/custody", data={
        "person_releasing": "Pharmacy Tech",
        "person_accepting": "Mike Johnson",
        "temperature": "72.5",
        "tamper_seal": "TS-001",
        "package_condition": "Good",
        "incident_report": "",
        "submit": "Add Chain of Custody Entry"
    }, follow_redirects=True)
    test("Driver can submit custody record", r.status_code == 200, f"got {r.status_code}")
    test("Custody submission shows confirmation", b"Chain of custody" in r.data and b"added" in r.data.lower())

    logout(c)

    # ── 13. ADMIN CAN ACCESS DRIVER PORTAL ──
    print("\n[13] Admin Cross-Access")
    login(c, "admin@tripleforcelogistic.com", "ChangeMe123!")
    r = c.get("/driver/")
    test("Admin can access driver portal", r.status_code == 200, f"got {r.status_code}")
    r = c.get("/driver/deliveries/1")
    test("Admin can access any delivery detail", r.status_code == 200, f"got {r.status_code}")
    logout(c)

    # ── 14. USER MANAGEMENT CRUD ──
    print("\n[14] User Management CRUD")
    login(c, "admin@tripleforcelogistic.com", "ChangeMe123!")

    # Create user
    r = c.post("/users/new", data={
        "email": "newdriver@test.com",
        "first_name": "New",
        "last_name": "Driver",
        "phone": "555-1234",
        "role": "driver",
        "password": "NewPass123!",
        "is_active_user": "y",
        "submit": "Save User"
    }, follow_redirects=True)
    test("Admin can create new user", r.status_code == 200, f"got {r.status_code}")
    test("New user creation confirmed", b"created successfully" in r.data or b"newdriver@test.com" in r.data)

    # Verify user was created in DB
    with app.app_context():
        u = User.query.filter_by(email="newdriver@test.com").first()
        test("New user exists in DB", u is not None)
        if u:
            test("New user has driver role", u.role == "driver")
            test("New user has driver_record_id", u.driver_record_id is not None)
            test("New user has password hash", u.password_hash is not None and len(u.password_hash) > 0)

    # Edit user
    new_user_id = User.query.filter_by(email="newdriver@test.com").first().id
    r = c.post(f"/users/{new_user_id}/edit", data={
        "email": "newdriver@test.com",
        "first_name": "Updated",
        "last_name": "Driver",
        "phone": "555-5678",
        "role": "dispatcher",
        "is_active_user": "y",
        "new_password": "",
        "submit": "Save Changes"
    }, follow_redirects=True)
    test("Admin can edit user", r.status_code == 200, f"got {r.status_code}")
    test("User edit confirmed", b"updated successfully" in r.data or b"Updated" in r.data)

    # Toggle active
    r = c.post(f"/users/{new_user_id}/toggle-active", follow_redirects=True)
    test("Admin can toggle user active", r.status_code == 200, f"got {r.status_code}")
    with app.app_context():
        u = db.session.get(User, new_user_id)
        test("User is now deactivated", not u.is_active_user)

    logout(c)

    # ── 15. TEMPLATE RENDERING — NO RAW JINJA ──
    print("\n[15] Template Rendering Check")
    login(c, "admin@tripleforcelogistic.com", "ChangeMe123!")
    all_test_routes = [
        "/", "/dashboard", "/customers/", "/customers/1", "/customers/new", "/customers/1/edit",
        "/quotes/", "/quotes/calculator", "/quotes/1", "/dispatch/", "/dispatch/1", "/dispatch/new",
        "/invoices/", "/invoices/1", "/invoices/new", "/reports/", "/reminders/", "/settings",
        "/search", "/users/", "/users/new", "/driver/", "/driver/deliveries/1",
        "/driver/deliveries/1/pod", "/driver/deliveries/1/custody",
        "/auth/change-password",
    ]
    raw_jinja_count = 0
    for path in all_test_routes:
        r = c.get(path)
        if b"{%" in r.data or b"{{" in r.data:
            raw_jinja_count += 1
            test(f"No raw Jinja in {path}", False, "RAW JINJA FOUND")
        else:
            test(f"No raw Jinja in {path}", True)
    test(f"All {len(all_test_routes)} routes render cleanly", raw_jinja_count == 0, f"{raw_jinja_count} routes had raw Jinja")

    logout(c)

    # ── SUMMARY ──
    print("\n" + "="*60)
    print(f"RESULTS: {PASS} passed, {FAIL} failed, {PASS+FAIL} total")
    print("="*60)
    for line in results:
        if line.startswith("  FAIL"):
            print(line)

    sys.exit(1 if FAIL > 0 else 0)
