"""Serviço de domínio para transições de estado de Atendimento, Orçamento e OS."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping, MutableMapping

from sqlalchemy.orm import Session

from backend.audit import ImmutableAuditLogStore
from backend.state_enums import EntityKind, TERMINAL_STATES
from backend.state_transitions import (
    TransitionError,
    TransitionValidator,
    atendimento_validator,
    auto_block_on_pending_part,
    orcamento_validator_v2,
    os_validator_v2,
)

from app.models.entities import (
    Estimate,
    ServiceRequest,
    StateTransitionEvent,
    WorkOrder,
)


class StateMachineError(TransitionError):
    """Erro específico do serviço de domínio."""


VALIDATORS: dict[EntityKind, TransitionValidator] = {
    EntityKind.ATENDIMENTO: atendimento_validator(),
    EntityKind.ORCAMENTO: orcamento_validator_v2(),
    EntityKind.OS: os_validator_v2(),
}


ENTITY_MODELS: dict[EntityKind, type] = {
    EntityKind.ATENDIMENTO: ServiceRequest,
    EntityKind.ORCAMENTO: Estimate,
    EntityKind.OS: WorkOrder,
}


@dataclass
class TransitionResult:
    entity_kind: EntityKind
    entity_id: int
    from_state: str
    to_state: str
    event: str
    auto_follow_up: list[str]


def _load_entity(db: Session, entity_kind: EntityKind, entity_id: int):
    model = ENTITY_MODELS[entity_kind]
    entity = db.get(model, entity_id)
    if entity is None:
        raise StateMachineError(
            f"{entity_kind.value} id={entity_id} não encontrado"
        )
    return entity


def _write_history(
    db: Session,
    *,
    entity_kind: EntityKind,
    entity_id: int,
    from_state: str,
    to_state: str,
    event: str,
    actor_user_id: int | None,
    actor_role: str,
    correlation_id: str | None,
    context: Mapping[str, object],
) -> StateTransitionEvent:
    serializable = {
        key: value
        for key, value in context.items()
        if isinstance(value, (str, int, float, bool, list, dict, type(None)))
        and key not in {"audit_store"}
    }
    record = StateTransitionEvent(
        entity_type=entity_kind.value,
        entity_id=entity_id,
        from_state=from_state,
        to_state=to_state,
        event=event,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        correlation_id=correlation_id,
        context_json=json.dumps(serializable, ensure_ascii=False, default=str),
    )
    db.add(record)
    return record


def apply_transition(
    db: Session,
    *,
    entity_kind: EntityKind,
    entity_id: int,
    target_state: str,
    event: str,
    profile: str,
    context: MutableMapping[str, object],
    actor_user_id: int | None,
    correlation_id: str | None = None,
) -> TransitionResult:
    """Aplica uma transição validando regras de domínio e registra histórico."""

    entity = _load_entity(db, entity_kind, entity_id)
    current_state = entity.status
    validator = VALIDATORS[entity_kind]

    # Regra de domínio: OS só nasce de orçamento aprovado.
    if entity_kind == EntityKind.OS and current_state == "aberta" and target_state == "em_execucao":
        if not context.get("budget_approved"):
            estimate_id = context.get("estimate_id") or entity.estimate_id
            if estimate_id:
                estimate = db.get(Estimate, int(estimate_id))
                if estimate is not None and estimate.status == "aprovado":
                    context["budget_approved"] = True

    context.setdefault("resource_id", entity_id)
    context.setdefault("actor_id", actor_user_id or "sistema")
    context.setdefault("correlation_id", correlation_id or "na")
    context.setdefault("audit_store", ImmutableAuditLogStore())

    validator.apply(
        current_state=current_state,
        target_state=target_state,
        event=event,
        profile=profile,
        context=context,
    )

    entity.status = target_state
    db.add(entity)

    _write_history(
        db,
        entity_kind=entity_kind,
        entity_id=entity_id,
        from_state=current_state,
        to_state=target_state,
        event=event,
        actor_user_id=actor_user_id,
        actor_role=profile,
        correlation_id=correlation_id,
        context=context,
    )

    auto_follow_up: list[str] = []

    # Regra de domínio: bloqueio automático se entrou em execução com peça pendente.
    if (
        entity_kind == EntityKind.OS
        and target_state == "em_execucao"
        and context.get("has_pending_parts")
    ):
        new_state = auto_block_on_pending_part(
            os_state=target_state,
            context=context,
        )
        if new_state != target_state:
            entity.status = new_state
            db.add(entity)
            _write_history(
                db,
                entity_kind=entity_kind,
                entity_id=entity_id,
                from_state=target_state,
                to_state=new_state,
                event="bloquear_por_peca",
                actor_user_id=None,
                actor_role="sistema",
                correlation_id=correlation_id,
                context=context,
            )
            auto_follow_up.append(new_state)
            target_state = new_state

    # Regra de domínio: orçamento convertido cria OS vinculada.
    if entity_kind == EntityKind.ORCAMENTO and target_state == "convertido":
        existing = (
            db.query(WorkOrder)
            .filter(WorkOrder.estimate_id == entity_id)
            .first()
        )
        if existing is None:
            work_order = WorkOrder(
                service_request_id=entity.service_request_id,
                estimate_id=entity_id,
                status="aberta",
            )
            db.add(work_order)
            db.flush()
            _write_history(
                db,
                entity_kind=EntityKind.OS,
                entity_id=work_order.id,
                from_state=None,
                to_state="aberta",
                event="criar_os_a_partir_de_orcamento",
                actor_user_id=actor_user_id,
                actor_role=profile,
                correlation_id=correlation_id,
                context={"estimate_id": entity_id},
            )

    db.commit()

    return TransitionResult(
        entity_kind=entity_kind,
        entity_id=entity_id,
        from_state=current_state,
        to_state=target_state,
        event=event,
        auto_follow_up=auto_follow_up,
    )


def list_history(
    db: Session,
    *,
    entity_kind: EntityKind,
    entity_id: int,
) -> list[StateTransitionEvent]:
    return (
        db.query(StateTransitionEvent)
        .filter(
            StateTransitionEvent.entity_type == entity_kind.value,
            StateTransitionEvent.entity_id == entity_id,
        )
        .order_by(StateTransitionEvent.created_at.asc(), StateTransitionEvent.id.asc())
        .all()
    )


def is_terminal(entity_kind: EntityKind, state: str) -> bool:
    return state in TERMINAL_STATES[entity_kind]
