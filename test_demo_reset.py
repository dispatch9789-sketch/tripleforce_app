"""Safety tests for the admin-only demo data reset."""

from datetime import datetime, timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import (
    Customer,
    CustomerAccountRequest,
    CustomerInvitation,
    Delivery,
    Expense,
    Invoice,
    Prospect,
    Quote,
    User,
)


class TestConfig:
    TESTING = True
    SECRET_KEY = "demo-reset-tests"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    UPLOAD_FOLDER = "/tmp/tripleforce-demo-reset-tests"
    AUTO_CREATE_SCHEMA = True


@pytest.fixture()
def seeded_app():
    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
        customer = Customer(business_name="Demo Facility", category="Laboratory")
        admin = User(email="admin@example.test", role="admin", is_active_user=True)
        dispatcher = User(email="dispatch@example.test", role="dispatcher", is_active_user=True)
        admin.set_password("AdminPass123!")
        dispatcher.set_password("DispatchPass123!")
        db.session.add_all([customer, admin, dispatcher])
        db.session.flush()
        customer_user = User(
            email="customer@example.test", role="customer",
            customer_id=customer.id, is_active_user=True,
        )
        customer_user.set_password("CustomerPass123!")
        delivery = Delivery(order_number="TF-1001", customer_id=customer.id)
        quote = Quote(quote_number="QT-1001", customer_id=customer.id)
        invoice = Invoice(invoice_number="INV-1001", customer_id=customer.id)
        expense = Expense(amount=25, category="Fuel")
        prospect = Prospect(organization_name="Preserved Prospect", dedupe_key="preserved prospect")
        request = CustomerAccountRequest(
            business_name="Demo Facility", contact_name="Demo Contact",
            email="customer@example.test", phone="5550100",
            customer_id=customer.id, user=customer_user,
        )
        db.session.add_all([customer_user, delivery, quote, invoice, expense, prospect, request])
        db.session.flush()
        invitation = CustomerInvitation(
            user_id=customer_user.id,
            token_hash="a" * 64,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db.session.add(invitation)
        db.session.commit()
        ids = {"admin": admin.id, "dispatcher": dispatcher.id}
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


def test_reset_requires_admin_and_exact_confirmation(seeded_app):
    app, ids = seeded_app
    dispatcher = logged_in_client(app, ids["dispatcher"])
    assert dispatcher.post(
        "/settings/clear-demo-data", data={"confirmation": "CLEAR DEMO DATA"}
    ).status_code == 403

    admin = logged_in_client(app, ids["admin"])
    response = admin.post(
        "/settings/clear-demo-data", data={"confirmation": "clear everything"}
    )
    assert response.status_code == 302
    with app.app_context():
        assert Customer.query.count() == 1
        assert Delivery.query.count() == 1


def test_reset_clears_demo_records_and_preserves_business_configuration(seeded_app):
    app, ids = seeded_app
    admin = logged_in_client(app, ids["admin"])
    response = admin.post(
        "/settings/clear-demo-data", data={"confirmation": "CLEAR DEMO DATA"}
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")

    with app.app_context():
        assert Customer.query.count() == 0
        assert Delivery.query.count() == 0
        assert Quote.query.count() == 0
        assert Invoice.query.count() == 0
        assert CustomerAccountRequest.query.count() == 0
        assert CustomerInvitation.query.count() == 0
        assert User.query.filter_by(role="customer").count() == 0
        assert User.query.filter(User.role.in_(["admin", "dispatcher", "driver"])).count() == 2
        assert Expense.query.count() == 1
        assert Prospect.query.count() == 1
