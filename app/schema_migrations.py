"""Idempotent runtime schema migrations for the public pickup-request fields.

Why this exists
---------------
Railway deploys this app with only ``gunicorn`` — there is no ``flask db
upgrade`` step in the deploy. The app factory calls ``db.create_all()`` on
startup, which creates *new* tables but does **not** add columns to *existing*
tables. So adding nullable columns to the ``deliveries`` model would not be
applied to an already-existing Railway database, and public pickup submissions
that set the new fields would fail to persist.

This helper is called immediately after ``db.create_all()`` in the app
factory. It inspects the ``deliveries`` table and, for every new
customer-form column that is missing, runs ``ALTER TABLE ... ADD COLUMN``.
It is safe to run on every boot and on a fresh database (where the columns
already exist, so it is a no-op). It works for both SQLite (local/dev) and
PostgreSQL (production), since both support ``ALTER TABLE ADD COLUMN`` for
nullable columns.

All added columns are nullable with no default, so existing rows are
preserved unchanged and existing data is never lost.
"""
import logging

from sqlalchemy import inspect, text

logger = logging.getLogger("tripleforce.schema")

# (column name, SQL type) for every new public pickup-request column.
# NOTE: "requested_delivery_deadline" reuses the existing ``delivery_deadline``
# column on the deliveries table, so it is intentionally not listed here.
_NEW_DELIVERY_COLUMNS = [
    ("company_facility_name", "VARCHAR(255)"),
    ("pickup_contact_phone", "VARCHAR(50)"),
    ("delivery_contact_phone", "VARCHAR(50)"),
    ("delivery_type", "VARCHAR(50)"),
    ("delivery_type_other", "VARCHAR(200)"),
    ("trip_type", "VARCHAR(30)"),
    ("reference_number", "VARCHAR(100)"),
    ("package_weight", "VARCHAR(50)"),
    ("package_size", "VARCHAR(100)"),
    ("is_recurring", "BOOLEAN"),
    ("recurring_route_notes", "TEXT"),
]

_NEW_PRICING_COLUMNS = [
    ("loaded_miles_included", "FLOAT DEFAULT 10"),
    ("loaded_mile_charge", "FLOAT DEFAULT 2"),
    ("deadhead_miles_included", "FLOAT DEFAULT 10"),
    ("deadhead_mile_charge", "FLOAT DEFAULT 1.25"),
    ("sunday_holiday_customer_quote", "BOOLEAN DEFAULT TRUE"),
    ("wait_time_included_minutes", "FLOAT DEFAULT 15"),
    ("wait_time_block_minutes", "FLOAT DEFAULT 15"),
    ("wait_time_per_block", "FLOAT DEFAULT 20"),
]


def ensure_delivery_columns(app, db):
    """Add any missing public-pickup columns to the deliveries table."""
    with app.app_context():
        inspector = inspect(db.engine)
        if "deliveries" not in inspector.get_table_names():
            # Fresh database — db.create_all() already created the full schema.
            return

        existing = {c["name"] for c in inspector.get_columns("deliveries")}
        added = []
        skipped = []
        with db.engine.begin() as conn:
            for col, coltype in _NEW_DELIVERY_COLUMNS:
                if col in existing:
                    continue
                try:
                    conn.execute(
                        text('ALTER TABLE deliveries ADD COLUMN "{col}" {ctype}'.format(
                            col=col, ctype=coltype
                        ))
                    )
                    added.append(col)
                except Exception:
                    # Another gunicorn worker may have just added this column.
                    # Re-check; if it now exists, this is the expected race and
                    # we simply skip it rather than failing the boot.
                    current = {c["name"] for c in inspect(db.engine).get_columns("deliveries")}
                    if col in current:
                        skipped.append(col)
                    else:
                        raise

        if added:
            logger.info("Schema migration: added deliveries columns: %s", ", ".join(added))
        if skipped:
            logger.info("Schema migration: columns already added by another worker: %s", ", ".join(skipped))


def seed_checklist_items(app, db):
    """Seed default checklist items if the table is empty.

    Called after db.create_all() so the checklist_items table exists.
    Idempotent: only seeds when the table has zero rows.
    """
    with app.app_context():
        inspector = inspect(db.engine)
        if "checklist_items" not in inspector.get_table_names():
            return

        from app.models import ChecklistItem, DEFAULT_CHECKLIST_ITEMS
        existing = db.session.query(ChecklistItem).count()
        if existing > 0:
            return
        for i, label in enumerate(DEFAULT_CHECKLIST_ITEMS):
            item = ChecklistItem(label=label, sort_order=i, is_active=True)
            db.session.add(item)
        db.session.commit()
        logger.info("Schema migration: seeded %d default checklist items", len(DEFAULT_CHECKLIST_ITEMS))


def ensure_pricing_columns(app, db):
    """Add editable rate-card columns without changing existing records."""
    with app.app_context():
        inspector = inspect(db.engine)
        if "pricing_settings" not in inspector.get_table_names():
            return
        existing = {c["name"] for c in inspector.get_columns("pricing_settings")}
        with db.engine.begin() as conn:
            for col, coltype in _NEW_PRICING_COLUMNS:
                if col not in existing:
                    conn.execute(text('ALTER TABLE pricing_settings ADD COLUMN "{col}" {ctype}'.format(col=col, ctype=coltype)))
