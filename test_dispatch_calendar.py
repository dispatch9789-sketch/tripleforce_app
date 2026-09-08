"""Regression checks for the dispatch board calendar view."""
import os
import sys
import tempfile
from datetime import datetime

os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.mktemp(suffix=".db")
os.environ["SECRET_KEY"] = "calendar-test-secret"
os.environ["FLASK_DEBUG"] = "0"

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from app.extensions import db
from app.models import Delivery, User


app = create_app()
app.config["TESTING"] = True
app.config["WTF_CSRF_ENABLED"] = False

with app.app_context():
    db.create_all()
    user = User(
        email="calendar@test.local", password_hash="x", role="dispatcher",
        first_name="Calendar", last_name="Tester", is_active_user=True,
    )
    delivery = Delivery(
        order_number="TF-CAL-1", pickup_datetime=datetime(2026, 9, 15, 14, 30),
        pickup_address="123 Pickup St", delivery_address="456 Delivery Ave",
        pickup_contact="Pickup Contact", status="Scheduled",
    )
    db.session.add_all([user, delivery])
    db.session.commit()
    user_id = user.id
    delivery_id = delivery.id

client = app.test_client()
with client.session_transaction() as session:
    session["_user_id"] = str(user_id)
    session["_fresh"] = True

response = client.get("/dispatch/?view=calendar&status=Scheduled")
body = response.get_data(as_text=True)
assert response.status_code == 200
assert 'href="/dispatch/?view=calendar&amp;status=Scheduled' in body
assert "calendarPrevious" in body and "calendarToday" in body and "calendarNext" in body
assert "TF-CAL-1" in body and '"pickup_date": "2026-09-15"' in body
assert "/dispatch/{0}".format(delivery_id) in body
assert "disabled" not in body.split('id="calendarPrevious"')[0]
print("ALL CALENDAR CHECKS PASSED")