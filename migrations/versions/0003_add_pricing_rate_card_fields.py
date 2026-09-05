"""add editable rate-card fields to pricing settings

Revision ID: 0003_pricing_rate_card
Revises: 0002_pickup_fields
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_pricing_rate_card"
down_revision = "0002_pickup_fields"
branch_labels = None
depends_on = None


_RATE_CARD_COLUMNS = [
    ("loaded_miles_included", sa.Float(), 10.0),
    ("loaded_mile_charge", sa.Float(), 2.0),
    ("deadhead_miles_included", sa.Float(), 10.0),
    ("deadhead_mile_charge", sa.Float(), 1.25),
    ("sunday_holiday_customer_quote", sa.Boolean(), True),
    ("wait_time_included_minutes", sa.Float(), 15.0),
    ("wait_time_block_minutes", sa.Float(), 15.0),
    ("wait_time_per_block", sa.Float(), 20.0),
]


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "pricing_settings" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("pricing_settings")}
    for name, column_type, default in _RATE_CARD_COLUMNS:
        if name not in existing:
            op.add_column("pricing_settings", sa.Column(name, column_type, nullable=True, server_default=sa.text(str(default).lower() if isinstance(default, bool) else str(default))))

    for name, _, _ in _RATE_CARD_COLUMNS:
        op.alter_column("pricing_settings", name, server_default=None)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "pricing_settings" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("pricing_settings")}
    for name, _, _ in reversed(_RATE_CARD_COLUMNS):
        if name in existing:
            op.drop_column("pricing_settings", name)
