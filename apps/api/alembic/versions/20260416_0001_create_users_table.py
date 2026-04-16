"""create initial workshop schema

Revision ID: 20260416_0001
Revises:
Create Date: 2026-04-16
"""

from datetime import datetime, timezone

import sqlalchemy as sa

from alembic import op
from app.db.base import Base
from app.models import entities  # noqa: F401

revision = "20260416_0001"
down_revision = None
branch_labels = None
depends_on = None


def _seed_roles_and_permissions() -> None:
    now = datetime.now(timezone.utc)

    roles_table = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("created_by", sa.Integer),
    )
    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("created_by", sa.Integer),
    )

    op.bulk_insert(
        roles_table,
        [
            {
                "id": 1,
                "code": "owner",
                "name": "Proprietário",
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            },
            {
                "id": 2,
                "code": "manager",
                "name": "Gerente",
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            },
            {
                "id": 3,
                "code": "mechanic",
                "name": "Mecânico",
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            },
            {
                "id": 4,
                "code": "attendant",
                "name": "Atendente",
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            },
            {
                "id": 5,
                "code": "finance",
                "name": "Financeiro",
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            },
        ],
    )

    op.bulk_insert(
        permissions_table,
        [
            {
                "id": 1,
                "code": "service_requests.read",
                "name": "Ver atendimentos",
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            },
            {
                "id": 2,
                "code": "service_requests.write",
                "name": "Gerenciar atendimentos",
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            },
            {
                "id": 3,
                "code": "work_orders.read",
                "name": "Ver ordens de serviço",
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            },
            {
                "id": 4,
                "code": "work_orders.write",
                "name": "Gerenciar ordens de serviço",
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            },
            {
                "id": 5,
                "code": "inventory.read",
                "name": "Ver estoque",
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            },
            {
                "id": 6,
                "code": "inventory.write",
                "name": "Movimentar estoque",
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            },
            {
                "id": 7,
                "code": "purchases.read",
                "name": "Ver compras",
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            },
            {
                "id": 8,
                "code": "purchases.write",
                "name": "Gerenciar compras",
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            },
            {
                "id": 9,
                "code": "finance.read",
                "name": "Ver financeiro",
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            },
            {
                "id": 10,
                "code": "finance.write",
                "name": "Gerenciar financeiro",
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            },
            {
                "id": 11,
                "code": "users.read",
                "name": "Ver usuários",
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            },
            {
                "id": 12,
                "code": "users.write",
                "name": "Gerenciar usuários",
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            },
        ],
    )


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    _seed_roles_and_permissions()


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
