from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.deps import get_db
from app.main import app
from app.models.entities import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)


def _prepare_db() -> tuple[sessionmaker, Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = local_session()

    user = User(
        id=1,
        name="Gerente",
        email="gerente@oficina.dev",
        password_hash=hash_password("SenhaSegura123"),
        is_active=True,
    )
    role = Role(id=1, code="manager", name="Gerente")
    db.add_all([user, role])
    db.flush()

    permissions = [
        Permission(id=1, code="cash.close", name="Fechar caixa"),
        Permission(id=2, code="estimate.approve", name="Aprovar orçamento"),
        Permission(id=3, code="purchase.approve", name="Aprovar compra"),
        Permission(id=4, code="attachment.manage", name="Fotos"),
        Permission(id=5, code="work_order.status_change", name="Status OS"),
        Permission(id=6, code="finance.value_change", name="Alteração de valor"),
    ]
    db.add_all(permissions)
    db.flush()

    db.add(UserRole(user_id=1, role_id=1))
    db.add_all(RolePermission(role_id=1, permission_id=permission.id) for permission in permissions)
    db.commit()

    return local_session, db


def _override_db(local_session: sessionmaker):
    def _get_db_override():
        db = local_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db_override


def test_login_and_refresh_token_rotation() -> None:
    local_session, _ = _prepare_db()
    _override_db(local_session)
    client = TestClient(app)

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "gerente@oficina.dev", "password": "SenhaSegura123"},
    )
    assert login_response.status_code == 200
    tokens = login_response.json()

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    rotated = refresh_response.json()
    assert rotated["refresh_token"] != tokens["refresh_token"]

    replay_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert replay_response.status_code == 401

    app.dependency_overrides.clear()


def test_critical_action_requires_granular_permission_and_writes_audit() -> None:
    local_session, _ = _prepare_db()
    _override_db(local_session)
    client = TestClient(app)

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "gerente@oficina.dev", "password": "SenhaSegura123"},
    )
    token = login_response.json()["access_token"]

    response = client.post(
        "/api/v1/critical-actions/cash-close",
        headers={"Authorization": f"Bearer {token}"},
        json={"entity_type": "cash_session", "entity_id": 10, "payload": {"reason": "turno"}},
    )
    assert response.status_code == 200

    forbidden = client.post(
        "/api/v1/critical-actions/cash-close",
        json={"entity_type": "cash_session", "entity_id": 11},
    )
    assert forbidden.status_code == 401

    with local_session() as db:
        from app.models.entities import AuditLog

        logs = db.query(AuditLog).all()
        assert len(logs) == 1
        assert logs[0].action == "cash.close"

    app.dependency_overrides.clear()
