"""create users table

Revision ID: 20260416_0001
Revises:
Create Date: 2026-04-16
"""

import sqlalchemy as sa

from alembic import op

revision = "20260416_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=180), nullable=False, unique=True),
    )


def downgrade() -> None:
    op.drop_table("users")
