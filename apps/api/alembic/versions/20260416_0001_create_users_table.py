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

    roles = [
        (1, "owner", "Proprietário"),
        (2, "manager", "Gerente"),
        (3, "mechanic", "Mecânico"),
        (4, "attendant", "Atendente"),
        (5, "finance", "Financeiro"),
    ]
    permissions = [
        (1, "service_requests.read", "Ver atendimentos"),
        (2, "service_requests.write", "Gerenciar atendimentos"),
        (3, "work_orders.read", "Ver ordens de serviço"),
        (4, "work_orders.write", "Gerenciar ordens de serviço"),
        (5, "inventory.read", "Ver estoque"),
        (6, "inventory.write", "Movimentar estoque"),
        (7, "purchases.read", "Ver compras"),
        (8, "purchases.write", "Gerenciar compras"),
        (9, "finance.read", "Ver financeiro"),
        (10, "finance.write", "Gerenciar financeiro"),
        (11, "users.read", "Ver usuários"),
        (12, "users.write", "Gerenciar usuários"),
        (13, "estimate.approve", "Aprovar orçamento"),
        (14, "purchase.approve", "Aprovar compra"),
        (15, "cash.close", "Fechar caixa"),
        (16, "finance.value_change", "Alterar valores financeiros"),
        (17, "work_order.status_change", "Alterar status da OS"),
        (18, "attachment.manage", "Upload/remoção de fotos"),
    ]

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
                "id": role_id,
                "code": code,
                "name": name,
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            }
            for role_id, code, name in roles
        ],
    )
    op.bulk_insert(
        permissions_table,
        [
            {
                "id": perm_id,
                "code": code,
                "name": name,
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            }
            for perm_id, code, name in permissions
        ],
    )

    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("id", sa.Integer),
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("created_by", sa.Integer),
    )

    owner_permission_ids = [perm[0] for perm in permissions]
    manager_permission_ids = [
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        13,
        14,
        15,
        16,
        17,
        18,
    ]
    finance_permission_ids = [9, 10, 14, 15, 16]

    mappings = []
    idx = 1
    for permission_id in owner_permission_ids:
        mappings.append((idx, 1, permission_id))
        idx += 1
    for permission_id in manager_permission_ids:
        mappings.append((idx, 2, permission_id))
        idx += 1
    for permission_id in finance_permission_ids:
        mappings.append((idx, 5, permission_id))
        idx += 1

    op.bulk_insert(
        role_permissions_table,
        [
            {
                "id": mapping_id,
                "role_id": role_id,
                "permission_id": permission_id,
                "created_at": now,
                "updated_at": now,
                "created_by": None,
            }
            for mapping_id, role_id, permission_id in mappings
        ],
    )


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    _seed_roles_and_permissions()


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
