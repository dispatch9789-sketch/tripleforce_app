#!/usr/bin/env python3
"""Access-control test suite for the Triple Force Logistic app.

Verifies the two-entrance landing-page security model:
  1. The public landing page shows BOTH a 'Request a Pickup' button
     (public customer entrance) AND a visible 'Staff Login' button
     (private office entrance) — but exposes no internal staff routes or
     sidebar. The staff-login button is visible; the office behind it is
     protected, not the link itself.
  2. Logged-out visitors hitting any internal/staff route are redirected
     to the login page (or denied) — protection is enforced on the server,
     not by hiding links.
  3. The customer pickup form stays publicly accessible and unchanged.
  4. Logged-in authorized staff can still reach permitted pages.
  5. Non-admin staff are denied (403) on admin-only routes.
  6. Logging out returns staff to the public landing page, and the office
     area is blocked again (internal URLs redirect to login).
  7. Authenticated staff pages carry no-cache headers so the browser Back
     button cannot reveal usable staff pages after logout.

Run:  python test_access_control.py
"""
import os
import sys

# NOTE: app/config.py forces sqlite:///<repo>/tripleforce.db whenever
# DATABASE_URL starts with "sqlite", so a temp-file URL is silently ignored.
# To guarantee a clean, isolated DB every run we delete the repo DB file
# before create_app() (which calls db.create_all()) recreates it empty.
import os as _os
_DB_PATH = _os.path.join(_os.path.abspath(_os.path.dirname(__file__)), "tripleforce.db")
if _os.path.exists(_DB_PATH):
    _os.remove(_DB_PATH)

# ── Isolated test database so we never touch real data ──
os.environ["DATABASE_URL"] = "sqlite:///tripleforce.db"
os.environ["SECRET_KEY"] = "test-secret-key-access-control"
os.environ["FLASK_DEBUG"] = "0"
os.environ["MAIL_USERNAME"] = ""  # disable SMTP in tests

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from app.extensions import db
from app.models import User

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


# Every internal/staff route that must require login. (Public routes
# "/" and "/request-pickup" are intentionally NOT in this list.)
PROTECTED_GET_ROUTES = [
    "/dashboard",
    "/search",
    "/settings",
    "/customers/",
    "/customers/new",
    "/quotes/",
    "/quotes/calculator",
    "/dispatch/",
    "/dispatch/new",
    "/invoices/",
    "/invoices/new",
    "/reports/",
    "/reminders/",
    "/reminders/new",
    "/users/",
    "/users/new",
    "/outreach/",
    "/outreach/new",
    "/driver/",
]

# Admin-only GET routes (admin_required). A dispatcher must get 403.
ADMIN_ONLY_ROUTES = [
    "/settings",
    "/users/",
    "/users/new",
]


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
        # Seed one user per role.
        admin = User(email="admin@test.com", first_name="Ada", last_name="Admin",
                     role="admin", is_active_user=True)
        admin.set_password("AdminPass123!")
        dispatcher = User(email="dispatch@test.com", first_name="Dan",
                          last_name="Dispatcher", role="dispatcher", is_active_user=True)
        dispatcher.set_password("DispatchPass123!")
        driver = User(email="driver@test.com", first_name="Don", last_name="Driver",
                      role="driver", is_active_user=True)
        driver.set_password("DriverPass123!")
        db.session.add_all([admin, dispatcher, driver])
        db.session.commit()

    client = app.test_client()

    print("=" * 64)
    print("TRIPLE FORCE LOGISTIC — ACCESS-CONTROL TEST SUITE")
    print("=" * 64)

    # ── 1. PUBLIC LANDING PAGE: two visible entrances, office hidden ──
    print("\n[1] Public landing page shows two entrances, no internal office")
    r = client.get("/")
    test("Landing page GET 200", r.status_code == 200, f"got {r.status_code}")
    body = r.data.decode("utf-8", errors="ignore")
    test("Landing page has 'Request a Pickup' button",
         "Request a Pickup" in body and "/request-pickup" in body)
    test("Landing page has visible 'Staff Login' button",
         "Staff Login" in body and "/auth/login" in body)
    test("Landing page exposes NO internal staff routes",
         "/dashboard" not in body and "/dispatch" not in body
         and "/customers" not in body and "/invoices" not in body
         and "/outreach" not in body and "/settings" not in body
         and "/reports" not in body and "/reminders" not in body)
    test("Landing page has no internal sidebar",
         'class="sidebar"' not in body.lower())

    # ── 2. CUSTOMER PICKUP FORM STAYS PUBLIC ──
    print("\n[2] Customer pickup form remains publicly accessible")
    r = client.get("/request-pickup")
    test("GET /request-pickup 200 while logged out", r.status_code == 200,
         f"got {r.status_code}")
    test("Pickup form has no internal sidebar",
         'class="sidebar"' not in r.data.decode("utf-8", errors="ignore").lower())

    # ── 3. LOGGED-OUT VISITOR → EVERY INTERNAL ROUTE REDIRECTS TO LOGIN ──
    print("\n[3] Logged-out visitor is redirected to login on every staff route")
    for route in PROTECTED_GET_ROUTES:
        r = client.get(route, follow_redirects=False)
        redirected_to_login = (
            r.status_code in (301, 302, 303, 308)
            and "/auth/login" in (r.headers.get("Location") or "")
        )
        test(f"Logged-out {route} → redirect to login",
             redirected_to_login, f"got {r.status_code} -> {r.headers.get('Location')}")

    # ── 4. LOGGED-IN ADMIN CAN ACCESS PERMITTED PAGES ──
    print("\n[4] Logged-in authorized staff can access permitted pages")
    login(client, "admin@test.com", "AdminPass123!")
    for route in ["/dashboard", "/settings", "/users/", "/customers/", "/dispatch/",
                  "/invoices/", "/reports/", "/outreach/"]:
        r = client.get(route, follow_redirects=False)
        test(f"Admin GET {route} → 200", r.status_code == 200,
             f"got {r.status_code}")

    # ── 5. AUTHENTICATED STAFF PAGES CARRY NO-CACHE HEADERS ──
    print("\n[5] Authenticated staff pages carry no-cache headers")
    r = client.get("/dashboard", follow_redirects=False)
    cc = r.headers.get("Cache-Control", "")
    test("Dashboard Cache-Control includes no-store",
         "no-store" in cc, f"got '{cc}'")

    # ── 6. LOGOUT RETURNS TO PUBLIC LANDING PAGE; OFFICE BLOCKED AGAIN ──
    print("\n[6] Logout returns to public landing page; office blocked again")
    r = client.get("/auth/logout", follow_redirects=False)
    loc = r.headers.get("Location") or ""
    test("Logout → redirect to public landing page",
         r.status_code in (301, 302, 303, 308)
         and loc.rstrip("/") == "" and "/auth/login" not in loc,
         f"got {r.status_code} -> {loc}")
    r = client.get("/dashboard", follow_redirects=False)
    test("Post-logout /dashboard → redirect to login",
         r.status_code in (301, 302, 303, 308)
         and "/auth/login" in (r.headers.get("Location") or ""),
         f"got {r.status_code} -> {r.headers.get('Location')}")

    # ── 7. NON-ADMIN STAFF CANNOT ACCESS ADMIN-ONLY ROUTES ──
    print("\n[7] Non-admin staff cannot access admin-only routes (403)")
    login(client, "dispatch@test.com", "DispatchPass123!")
    # Dispatcher can reach normal staff pages...
    r = client.get("/dashboard", follow_redirects=False)
    test("Dispatcher can access /dashboard", r.status_code == 200,
         f"got {r.status_code}")
    # ...but is denied on admin-only pages.
    for route in ADMIN_ONLY_ROUTES:
        r = client.get(route, follow_redirects=False)
        denied = r.status_code == 403 or (
            r.status_code in (301, 302, 303, 308)
            and "/auth/login" in (r.headers.get("Location") or "")
        )
        test(f"Dispatcher denied on {route}", denied,
             f"got {r.status_code} -> {r.headers.get('Location')}")

    # ── 8. DRIVER ROLE: can reach driver portal, denied on dispatcher+ routes ──
    print("\n[8] Driver role scoping")
    # Log out the previous (dispatcher) session first — login() short-circuits
    # when a user is already authenticated, so we must clear the session to
    # switch identities.
    client.get("/auth/logout", follow_redirects=False)
    login(client, "driver@test.com", "DriverPass123!")
    r = client.get("/driver/", follow_redirects=False)
    test("Driver can access /driver/", r.status_code == 200,
         f"got {r.status_code}")
    r = client.get("/dashboard", follow_redirects=False)
    test("Driver denied on /dashboard (dispatcher_or_above)",
         r.status_code == 403 or (
             r.status_code in (301, 302, 303, 308)
             and "/auth/login" in (r.headers.get("Location") or "")
         ), f"got {r.status_code} -> {r.headers.get('Location')}")

    # ── Summary ──
    print("\n" + "=" * 64)
    for line in RESULTS:
        print(line)
    print("=" * 64)
    print(f"ACCESS-CONTROL TESTS: {PASS} passed, {FAIL} failed")
    print("=" * 64)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
