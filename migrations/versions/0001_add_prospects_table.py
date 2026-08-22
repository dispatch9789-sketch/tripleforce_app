"""add prospects table (Outreach Tracker)

Revision ID: 0001_prospects
Revises:
Create Date: 2026-08-22

Focused migration for the Outreach Tracker. Idempotent: it checks whether the
``prospects`` table already exists before creating it, so it is safe to run even
when ``db.create_all()`` (the app's normal startup table-creation path) has
already created the table.
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_prospects"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "prospects" in inspector.get_table_names():
        return

    op.create_table(
        "prospects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_name", sa.String(length=255), nullable=False),
        sa.Column("organization_type", sa.String(length=100)),
        sa.Column("contact_person", sa.String(length=200)),
        sa.Column("contact_title", sa.String(length=200)),
        sa.Column("email", sa.String(length=255)),
        sa.Column("phone", sa.String(length=50)),
        sa.Column("website", sa.String(length=255)),
        sa.Column("procurement_vendor_route", sa.String(length=255)),
        sa.Column("outreach_subject", sa.String(length=255)),
        sa.Column("outreach_status", sa.String(length=50)),
        sa.Column("date_contacted", sa.Date()),
        sa.Column("follow_up_date", sa.Date()),
        sa.Column("response_status", sa.String(length=100)),
        sa.Column("vendor_application_date", sa.Date()),
        sa.Column("vendor_registration_status", sa.String(length=50)),
        sa.Column("opportunity_stage", sa.String(length=50)),
        sa.Column("notes", sa.Text()),
        sa.Column("dedupe_key", sa.String(length=255)),
        sa.Column("archived", sa.Boolean()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_prospects_organization_name", "prospects", ["organization_name"])
    op.create_index("ix_prospects_outreach_status", "prospects", ["outreach_status"])
    op.create_index("ix_prospects_follow_up_date", "prospects", ["follow_up_date"])
    op.create_index("ix_prospects_opportunity_stage", "prospects", ["opportunity_stage"])
    op.create_index("ix_prospects_archived", "prospects", ["archived"])
    op.create_index("ix_prospects_dedupe_key", "prospects", ["dedupe_key"], unique=True)


def downgrade():
    op.drop_index("ix_prospects_archived", table_name="prospects")
    op.drop_index("ix_prospects_dedupe_key", table_name="prospects")
    op.drop_index("ix_prospects_opportunity_stage", table_name="prospects")
    op.drop_index("ix_prospects_follow_up_date", table_name="prospects")
    op.drop_index("ix_prospects_outreach_status", table_name="prospects")
    op.drop_index("ix_prospects_organization_name", table_name="prospects")
    op.drop_table("prospects")
