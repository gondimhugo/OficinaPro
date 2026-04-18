from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.deps import get_db
from app.main import app
from app.models.entities import (
    Client,
    Estimate,
    Permission,
    Role,
    RolePermission,
    ServiceRequest,
    StateTransitionEvent,
    User,
    UserRole,
    Vehicle,
    WorkOrder,
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
        name="Supervisor",
        email="super@oficina.dev",
        password_hash=hash_password("SenhaSegura123"),
        is_active=True,
    )
    role = Role(id=1, code="supervisor", name="Supervisor")
    db.add_all([user, role])
    db.flush()

    permissions = [
        Permission(id=1, code="work_order.status_change", name="Status OS"),
        Permission(id=2, code="estimate.approve", name="Aprovar orçamento"),
    ]
    db.add_all(permissions)
    db.flush()
    db.add(UserRole(user_id=1, role_id=1))
    db.add_all(
        RolePermission(role_id=1, permission_id=permission.id)
        for permission in permissions
    )

    client = Client(id=1, name="Cliente Demo")
    vehicle = Vehicle(id=1, client_id=1, plate="ABC1D23", model="Uno")
    sr = ServiceRequest(
        id=1,
        client_id=1,
        vehicle_id=1,
        status="aberto",
        complaint="ruído no motor",
    )
    estimate = Estimate(
        id=1,
        service_request_id=1,
        status="aprovado",
        total_amount=Decimal("500.00"),
    )
    work_order = WorkOrder(
        id=1, service_request_id=1, estimate_id=1, status="aberta"
    )
    db.add_all([client, vehicle, sr, estimate, work_order])
    db.commit()

    return local_session, db


def _override_db(local_session: sessionmaker) -> None:
    def _get_db_override():
        db = local_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db_override


def _token(client: TestClient) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "super@oficina.dev", "password": "SenhaSegura123"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_atendimento_transition_and_history() -> None:
    local_session, _ = _prepare_db()
    _override_db(local_session)
    client = TestClient(app)
    token = _token(client)

    resp = client.post(
        "/api/v1/state-machine/atendimentos/1/transitions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "target_state": "em_avaliacao",
            "event": "iniciar_avaliacao",
            "profile": "atendimento",
            "context": {"has_customer": True, "complaint_registered": True},
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["to_state"] == "em_avaliacao"
    assert body["from_state"] == "aberto"

    history = client.get(
        "/api/v1/state-machine/atendimento/1/events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert history.status_code == 200
    events = history.json()
    assert len(events) == 1
    assert events[0]["event"] == "iniciar_avaliacao"

    app.dependency_overrides.clear()


def test_os_requires_approved_budget_and_auto_blocks_on_pending_part() -> None:
    local_session, _ = _prepare_db()
    _override_db(local_session)
    client = TestClient(app)
    token = _token(client)

    resp = client.post(
        "/api/v1/state-machine/os/1/transitions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "target_state": "em_execucao",
            "event": "iniciar_execucao",
            "profile": "supervisor",
            "context": {"has_pending_parts": False},
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["to_state"] == "em_execucao"

    with local_session() as db:
        db.query(WorkOrder).filter(WorkOrder.id == 1).update({"status": "aberta"})
        db.commit()

    resp2 = client.post(
        "/api/v1/state-machine/os/1/transitions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "target_state": "em_execucao",
            "event": "iniciar_execucao",
            "profile": "supervisor",
            "context": {"has_pending_parts": True, "budget_approved": True},
        },
    )
    assert resp2.status_code == 422

    app.dependency_overrides.clear()


def test_os_auto_block_when_entering_execution_with_pending_part() -> None:
    local_session, _ = _prepare_db()
    _override_db(local_session)
    client = TestClient(app)
    token = _token(client)

    with local_session() as db:
        db.query(WorkOrder).filter(WorkOrder.id == 1).update({"status": "bloqueada_peca"})
        db.commit()

    resp = client.post(
        "/api/v1/state-machine/os/1/transitions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "target_state": "em_execucao",
            "event": "retomar_apos_peca",
            "profile": "supervisor",
            "context": {"has_pending_parts": False},
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["to_state"] == "em_execucao"

    app.dependency_overrides.clear()


def test_orcamento_conversion_creates_os() -> None:
    local_session, _ = _prepare_db()
    _override_db(local_session)
    client = TestClient(app)
    token = _token(client)

    with local_session() as db:
        db.query(WorkOrder).filter(WorkOrder.id == 1).delete()
        db.query(Estimate).filter(Estimate.id == 1).update({"status": "aprovado"})
        db.commit()

    resp = client.post(
        "/api/v1/state-machine/orcamentos/1/transitions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "target_state": "convertido",
            "event": "converter_em_os",
            "profile": "admin",
            "context": {"budget_approved": True},
        },
    )
    assert resp.status_code == 200, resp.text

    with local_session() as db:
        work_orders = db.query(WorkOrder).all()
        assert len(work_orders) == 1
        assert work_orders[0].estimate_id == 1
        assert work_orders[0].status == "aberta"

        events = db.query(StateTransitionEvent).filter_by(entity_type="os").all()
        assert any(e.event == "criar_os_a_partir_de_orcamento" for e in events)

    app.dependency_overrides.clear()
