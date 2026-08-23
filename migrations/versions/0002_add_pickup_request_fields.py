"""add public pickup-request operational fields to deliveries

Revision ID: 0002_pickup_fields
Revises: 0001_prospects
Create Date: 2026-08-23

Idempotent: it only adds columns that are missing, so it is safe to run even
when the app's runtime ``ensure_delivery_columns()`` helper (called on
startup) has already added them, or when ``db.create_all()`` created the
table fresh with the full schema.
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_pickup_fields"
down_revision = "0001_prospects"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "deliveries" not in inspector.get_table_names():
        return  # nothing to migrate yet

    existing = {c["name"] for c in inspector.get_columns("deliveries")}

    # NOTE: "requested_delivery_deadline" reuses the existing delivery_deadline
    # column, so it is intentionally not added here.
    new_columns = [
        ("company_facility_name", sa.String(length=255)),
        ("pickup_contact_phone", sa.String(length=50)),
        ("delivery_contact_phone", sa.String(length=50)),
        ("delivery_type", sa.String(length=50)),
        ("delivery_type_other", sa.String(length=200)),
        ("trip_type", sa.String(length=30)),
        ("reference_number", sa.String(length=100)),
        ("package_weight", sa.String(length=50)),
        ("package_size", sa.String(length=100)),
        ("is_recurring", sa.Boolean()),
        ("recurring_route_notes", sa.Text()),
    ]

    for col, coltype in new_columns:
        if col not in existing:
            op.add_column("deliveries", sa.Column(col, coltype, nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "deliveries" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("deliveries")}
    for col in [
        "recurring_route_notes", "is_recurring", "package_size", "package_weight",
        "reference_number", "trip_type", "delivery_type_other", "delivery_type",
        "delivery_contact_phone", "pickup_contact_phone", "company_facility_name",
    ]:
        if col in existing:
            op.drop_column("deliveries", col)
