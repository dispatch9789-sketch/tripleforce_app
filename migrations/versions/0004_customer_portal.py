"""add customer portal accounts and approval requests

Revision ID: 0004_customer_portal
Revises: 0003_pricing_rate_card
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_customer_portal"
down_revision = "0003_pricing_rate_card"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("customer_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_users_customer_id_customers", "customers", ["customer_id"], ["id"])
    op.create_index("ix_users_customer_id", "users", ["customer_id"])
    op.create_table(
        "customer_account_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("business_name", sa.String(255), nullable=False),
        sa.Column("contact_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("reviewed_by_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("review_reason", sa.String(500)),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id")),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
    )
    op.create_index("ix_customer_account_requests_email", "customer_account_requests", ["email"])
    op.create_index("ix_customer_account_requests_status", "customer_account_requests", ["status"])
    op.create_table(
        "customer_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("redeemed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_customer_invitations_user_id", "customer_invitations", ["user_id"], unique=True)


def downgrade():
    op.drop_index("ix_customer_invitations_user_id", table_name="customer_invitations")
    op.drop_table("customer_invitations")
    op.drop_index("ix_customer_account_requests_status", table_name="customer_account_requests")
    op.drop_index("ix_customer_account_requests_email", table_name="customer_account_requests")
    op.drop_table("customer_account_requests")
    op.drop_index("ix_users_customer_id", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("fk_users_customer_id_customers", type_="foreignkey")
        batch.drop_column("customer_id")
