#!/usr/bin/env python3
"""Self-contained functional tests for the Outreach Tracker integration.

Uses a throwaway SQLite DB (via TestConfig) so it passes on a fresh checkout
with no CSV and no prospect data — and proves db.create_all() creates the
prospects table without running `flask db upgrade` (the Railway path).
"""
import os
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.getcwd())

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import User, Prospect
from sqlalchemy import inspect as sa_inspect

TEST_DB = "/tmp/test_outreach.db"


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{TEST_DB}"
    TESTING = True
    WTF_CSRF_ENABLED = False
    DEBUG = False


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


# Fresh DB each run
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

app = create_app(TestConfig)

with app.app_context():
    db.create_all()
    # Prove create_all built the prospects table (no migration run)
    test("create_all creates prospects table", sa_inspect(db.engine).has_table("prospects"), "prospects table missing")

    # Synthetic admin + 3 prospects (no dependency on the real CSV / DB)
    admin = User(email="admin@testcompany.com", role="admin")
    admin.set_password("TestPass123!")
    db.session.add(admin)
    for i, (org, email) in enumerate([
        ("Acme Labs", "ops@acmelabs.test"),
        ("Beta Imaging", "info@betaimaging.test"),
        ("Gamma Pathology", "lab@gammapath.test"),
    ]):
        p = Prospect(
            organization_name=org,
            organization_type="Laboratory" if i != 1 else "Imaging Center",
            contact_person=f"Contact {i+1}",
            email=email,
            phone=f"973-555-100{i}",
            outreach_status="Drafted - Pending Approval",
            vendor_registration_status="Not Started",
            opportunity_stage="Prospect",
            dedupe_key=Prospect.build_dedupe_key(org, email, f"973-555-100{i}"),
        )
        db.session.add(p)
    db.session.commit()

    client = app.test_client()
    SEED = 3

    # ── Auth gate: unauthenticated redirect ──
    r = client.get("/outreach/", follow_redirects=False)
    test("auth gate redirects unauthenticated", r.status_code in (301, 302), f"got {r.status_code}")

    # ── Login ──
    r = client.post("/auth/login", data={
        "email": "admin@testcompany.com",
        "password": "TestPass123!",
        "remember": "y",
    }, follow_redirects=False)
    test("admin login", r.status_code in (301, 302), f"got {r.status_code}")

    baseline = Prospect.query.filter_by(archived=False).count()
    test("synthetic prospects seeded", baseline == SEED, f"got {baseline}")

    # ── Dashboard / list ──
    r = client.get("/outreach/")
    test("index loads (dashboard + table)", r.status_code == 200 and b"Outreach Tracker" in r.data and b"Total Prospects" in r.data, f"got {r.status_code}")
    test("index shows prospects", b"Acme Labs" in r.data, "prospect not in table")

    # ── Filter ──
    r = client.get("/outreach/?status=Sent")
    test("filter by status works", r.status_code == 200, f"got {r.status_code}")

    # ── View detail ──
    first = Prospect.query.filter_by(archived=False).order_by(Prospect.organization_name).first()
    r = client.get(f"/outreach/{first.id}")
    test("view detail loads", r.status_code == 200 and first.organization_name.encode() in r.data, f"got {r.status_code}")

    # ── Add prospect (normal) ──
    r = client.post("/outreach/new", data={
        "organization_name": "Test Lab Integration",
        "organization_type": "Laboratory",
        "contact_person": "Jane Doe",
        "email": "jane@testlab.com",
        "phone": "973-555-9999",
        "outreach_status": "Drafted - Pending Approval",
        "vendor_registration_status": "Not Started",
        "opportunity_stage": "Prospect",
    }, follow_redirects=False)
    test("add prospect redirects (created)", r.status_code in (301, 302), f"got {r.status_code}")
    test("add prospect persisted", Prospect.query.filter_by(organization_name="Test Lab Integration").count() == 1, "not in db")
    test("dedupe_key computed", Prospect.query.filter_by(organization_name="Test Lab Integration").one().dedupe_key == "test lab integration|jane@testlab.com", "wrong key")

    # ── Duplicate (graceful, no 500) ──
    r = client.post("/outreach/new", data={
        "organization_name": "Test Lab Integration",
        "email": "jane@testlab.com",
        "outreach_status": "Drafted - Pending Approval",
        "vendor_registration_status": "Not Started",
        "opportunity_stage": "Prospect",
    }, follow_redirects=False)
    test("duplicate add rejected gracefully", r.status_code == 200 and b"already exists" in r.data, f"got {r.status_code}")
    test("duplicate not created", Prospect.query.filter_by(organization_name="Test Lab Integration").count() == 1, "dup created")

    pid = Prospect.query.filter_by(organization_name="Test Lab Integration").one().id

    # ── Edit (recompute dedupe key) ──
    r = client.post(f"/outreach/{pid}/edit", data={
        "organization_name": "Test Lab Integration",
        "email": "jane2@testlab.com",
        "outreach_status": "Ready to Send",
        "vendor_registration_status": "Not Started",
        "opportunity_stage": "Prospect",
    }, follow_redirects=False)
    p = Prospect.query.get(pid)
    test("edit redirects", r.status_code in (301, 302), f"got {r.status_code}")
    test("edit recomputed dedupe_key", p.dedupe_key == "test lab integration|jane2@testlab.com", f"got {p.dedupe_key}")
    test("edit saved email", p.email == "jane2@testlab.com", f"got {p.email}")

    # ── Mark sent ──
    r = client.post(f"/outreach/{pid}/mark-sent", follow_redirects=False)
    p = Prospect.query.get(pid)
    test("mark_sent sets status + date", p.outreach_status == "Sent" and p.date_contacted == date.today(), f"status={p.outreach_status} date={p.date_contacted}")

    # ── Follow-up date ──
    fu = date.today() + timedelta(days=4)
    r = client.post(f"/outreach/{pid}/followup", data={
        "follow_up_date": fu.strftime("%Y-%m-%d"),
        "outreach_status": "Follow-Up Needed",
    }, follow_redirects=False)
    p = Prospect.query.get(pid)
    test("followup sets date + status", p.follow_up_date == fu and p.outreach_status == "Follow-Up Needed", f"fu={p.follow_up_date} status={p.outreach_status}")

    # ── Status / stage / vendor reg ──
    r = client.post(f"/outreach/{pid}/status", data={
        "outreach_status": "Responded",
        "opportunity_stage": "Vendor Registration",
        "vendor_registration_status": "Started",
        "response_status": "Requested vendor portal",
    }, follow_redirects=False)
    p = Prospect.query.get(pid)
    test("status update saved", p.outreach_status == "Responded" and p.opportunity_stage == "Vendor Registration" and p.vendor_registration_status == "Started" and p.response_status == "Requested vendor portal", f"status={p.outreach_status} stage={p.opportunity_stage} vr={p.vendor_registration_status}")

    # ── Notes (append) ──
    client.post(f"/outreach/{pid}/notes", data={"notes": "First note from test"})
    client.post(f"/outreach/{pid}/notes", data={"notes": "Second note from test"})
    p = Prospect.query.get(pid)
    test("notes appended in order", "First note from test" in p.notes and "Second note from test" in p.notes and p.notes.index("First") < p.notes.index("Second"), f"notes={p.notes!r}")

    # ── Archive (soft delete) ──
    r = client.post(f"/outreach/{pid}/delete", follow_redirects=False)
    p = Prospect.query.get(pid)
    test("archive sets archived=True", p.archived is True, f"archived={p.archived}")
    test("archived hidden from default list", Prospect.query.filter_by(archived=False).count() == SEED, "count changed")

    # ── CSV import route (idempotent, dedup) — self-contained temp CSV ──
    import csv as _csv, io as _io, tempfile as _tf
    existing = Prospect.query.filter_by(archived=False).first()
    buf = _io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["Organization", "Facility Type", "Email", "Status", "Opportunity Stage"])
    w.writerow([existing.organization_name, existing.organization_type or "", existing.email or "", "Drafted", "Prospect"])
    tmp = _tf.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", newline="")
    tmp.write(buf.getvalue()); tmp.close()
    with open(tmp.name, "rb") as f:
        r = client.post("/outreach/import", data={"csv_file": (f, "t.csv")}, content_type="multipart/form-data", follow_redirects=False)
    test("csv import route idempotent (skip dup)", r.status_code in (301, 302), f"got {r.status_code}")
    test("import did not duplicate", Prospect.query.filter_by(organization_name=existing.organization_name).count() == 1, "dup created")
    os.remove(tmp.name)

    # ── Persistence after "refresh" ──
    p = Prospect.query.get(pid)
    test("persistence after refresh", p.outreach_status == "Responded" and p.vendor_registration_status == "Started" and "First note from test" in p.notes, "state not persisted")

print("\n" + "=" * 60)
for line in results:
    print(line)
print("=" * 60)
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
