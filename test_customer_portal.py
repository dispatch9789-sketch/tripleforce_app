"""Focused tenant-isolation tests; uses an isolated in-memory database."""
import pytest
import re
from app import create_app
from app.extensions import db
from app.models import Customer, CustomerAccountRequest, Delivery, Invoice, User


class TestConfig:
    TESTING = True
    SECRET_KEY = "customer-portal-tests"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    UPLOAD_FOLDER = "/tmp/tripleforce-customer-portal-tests"
    AUTO_CREATE_SCHEMA = True
    MAIL_USERNAME = ""


@pytest.fixture()
def setup_app():
    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
        a = Customer(business_name="Facility A", category="Laboratory", status="active")
        b = Customer(business_name="Facility B", category="Laboratory", status="active")
        db.session.add_all([a, b])
        db.session.flush()
        users = []
        for email, role, customer_id in [("a@example.test", "customer", a.id), ("b@example.test", "customer", b.id), ("staff@example.test", "dispatcher", None), ("admin@example.test", "admin", None)]:
            u = User(email=email, role=role, customer_id=customer_id, is_active_user=True)
            u.set_password("PortalPass123!")
            users.append(u)
        da = Delivery(order_number="A-1", customer_id=a.id, status="Delivered")
        db_delivery = Delivery(order_number="B-1", customer_id=b.id, status="In Transit")
        ia = Invoice(invoice_number="IA-1", customer_id=a.id, status="Sent", total_due=80, balance_due=80)
        ib = Invoice(invoice_number="IB-1", customer_id=b.id, status="Sent", total_due=90, balance_due=90)
        hidden = Invoice(invoice_number="IA-DRAFT", customer_id=a.id, status="Draft")
        db.session.add_all(users + [da, db_delivery, ia, ib, hidden])
        db.session.commit()
        ids = {"a": users[0].id, "b": users[1].id, "staff": users[2].id,
               "admin": users[3].id, "da": da.id, "db": db_delivery.id,
               "ia": ia.id, "ib": ib.id, "draft": hidden.id}
    yield app, ids
    with app.app_context():
        db.session.remove()
        db.drop_all()


def logged_in_client(app, user_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    return client


def test_customer_portal_only_shows_own_records(setup_app):
    app, ids = setup_app
    c = logged_in_client(app, ids["a"])
    assert c.get("/customer/").status_code == 200
    assert b"A-1" in c.get("/customer/deliveries").data
    assert b"B-1" not in c.get("/customer/deliveries").data
    denied_delivery = c.get(f"/customer/deliveries/{ids['db']}")
    assert denied_delivery.status_code == 404
    assert b"CUSTOMER PORTAL" in denied_delivery.data
    assert b"sidebar" not in denied_delivery.data.lower()
    assert b"IA-1" in c.get("/customer/invoices").data
    assert b"IB-1" not in c.get("/customer/invoices").data
    assert b"IA-DRAFT" not in c.get("/customer/invoices").data
    assert c.get(f"/customer/invoices/{ids['ib']}").status_code == 404


def test_customer_cannot_enter_staff_driver_or_approval_pages(setup_app):
    app, ids = setup_app
    c = logged_in_client(app, ids["a"])
    for path in ["/dashboard", "/dispatch/", "/invoices/", "/driver/", "/users/", "/customer-access/admin"]:
        assert c.get(path).status_code == 403, path


def test_staff_and_anonymous_cannot_enter_customer_data(setup_app):
    app, ids = setup_app
    assert app.test_client().get("/customer/").status_code in (302, 401)
    c = logged_in_client(app, ids["staff"])
    assert c.get("/customer/").status_code == 403


def test_customer_request_does_not_create_login(setup_app):
    app, _ = setup_app
    c = app.test_client()
    response = c.post("/customer-access/request", data={
        "business_name": "New Facility", "contact_name": "Taylor Contact",
        "email": "taylor@example.com", "phone": "2015550100",
    })
    assert response.status_code == 202
    with app.app_context():
        req = CustomerAccountRequest.query.filter_by(email="taylor@example.com").one()
        assert req.status == "pending"
        assert User.query.filter_by(email="taylor@example.com").first() is None


def test_non_admin_cannot_approve(setup_app):
    app, ids = setup_app
    with app.app_context():
        request = CustomerAccountRequest(business_name="New", contact_name="Person", email="p@example.test", phone="555")
        db.session.add(request)
        db.session.commit()
        request_id = request.id
    c = logged_in_client(app, ids["staff"])
    assert c.get("/customer-access/admin").status_code == 403
    assert c.get(f"/customer-access/admin/{request_id}").status_code == 403


def test_admin_approval_creates_linked_inactive_account_and_single_use_invite(setup_app, monkeypatch):
    app, ids = setup_app
    with app.app_context():
        request = CustomerAccountRequest(business_name="New Facility", contact_name="Taylor Contact",
                                         email="new-contact@example.com", phone="2015550110")
        db.session.add(request)
        db.session.commit()
        request_id = request.id
        customer_id = Customer.query.filter_by(business_name="Facility A").one().id
    outbound = {}
    def fake_send(to, subject, body):
        outbound["to"] = to
        outbound["body"] = body
        return True
    monkeypatch.setattr("app.customer_accounts.routes.send_email", fake_send)
    c = logged_in_client(app, ids["admin"])
    response = c.post(f"/customer-access/admin/{request_id}", data={
        "customer_id": str(customer_id), "review_reason": "Verified by staff",
    })
    assert response.status_code == 302
    with app.app_context():
        user = User.query.filter_by(email="new-contact@example.com").one()
        assert user.role == "customer" and user.customer_id == customer_id and not user.is_active_user
        assert CustomerAccountRequest.query.get(request_id).status == "approved"
        assert outbound["to"] == user.email
    token = outbound["body"].split("/customer-access/activate/")[1].strip()
    assert c.get(f"/customer-access/activate/{token}").status_code == 200
    response = c.post(f"/customer-access/activate/{token}", data={
        "password": "NewPassword123!", "confirm": "NewPassword123!",
    })
    assert response.status_code == 302
    with app.app_context():
        user = User.query.filter_by(email="new-contact@example.com").one()
        assert user.is_active_user and user.check_password("NewPassword123!")
    assert c.post(f"/customer-access/activate/{token}", data={
        "password": "OtherPassword123!", "confirm": "OtherPassword123!",
    }).status_code == 404


def test_broken_customer_link_fails_closed(setup_app):
    app, _ = setup_app
    with app.app_context():
        user = User(email="broken@example.test", role="customer", customer_id=None, is_active_user=True)
        user.set_password("PortalPass123!")
        db.session.add(user)
        db.session.commit()
        uid = user.id
    c = logged_in_client(app, uid)
    assert c.get("/customer/").status_code == 403


def test_private_upload_urls_are_not_public(setup_app):
    app, _ = setup_app
    c = app.test_client()
    assert c.get("/static/uploads/signatures/known.png").status_code == 404
    assert c.get("/static/uploads/contracts/known.pdf").status_code == 404


def test_signup_enforces_csrf_when_enabled(setup_app):
    app, _ = setup_app
    app.config["WTF_CSRF_ENABLED"] = True
    assert app.test_client().post("/customer-access/request", data={
        "business_name": "New", "contact_name": "Person", "email": "p@example.test", "phone": "555",
    }).status_code == 400


def test_approval_checks_role_after_valid_csrf_and_requires_csrf(setup_app):
    app, ids = setup_app
    app.config["WTF_CSRF_ENABLED"] = True
    with app.app_context():
        account_request = CustomerAccountRequest(business_name="New", contact_name="Person",
                                                 email="role@example.com", phone="555")
        db.session.add(account_request)
        db.session.commit()
        request_id = account_request.id
    admin = logged_in_client(app, ids["admin"])
    no_token = admin.post(f"/customer-access/admin/{request_id}", data={"customer_id": "1"})
    assert no_token.status_code == 400

    dispatcher = app.test_client()
    page = dispatcher.get("/customer-access/request")
    match = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', page.data)
    assert match
    with dispatcher.session_transaction() as session:
        session["_user_id"] = str(ids["staff"])
        session["_fresh"] = True
    denied = dispatcher.post(f"/customer-access/admin/{request_id}", data={
        "customer_id": "1", "csrf_token": match.group(1).decode(),
    })
    assert denied.status_code == 403
