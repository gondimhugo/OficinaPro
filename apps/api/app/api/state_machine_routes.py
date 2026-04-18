from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.deps import get_db
from app.models.entities import User
from app.schemas.state_machine import (
    StateEventItem,
    TransitionRequest,
    TransitionResponse,
)
from app.services.state_machine import (
    StateMachineError,
    apply_transition,
    list_history,
)

from backend.state_enums import EntityKind
from backend.state_transitions import (
    PreconditionError,
    TransitionError,
    UnauthorizedProfileError,
)

router = APIRouter(prefix="/state-machine", tags=["state-machine"])


def _dispatch(
    entity_kind: EntityKind,
    entity_id: int,
    payload: TransitionRequest,
    db: Session,
    user: User,
) -> TransitionResponse:
    try:
        result = apply_transition(
            db,
            entity_kind=entity_kind,
            entity_id=entity_id,
            target_state=payload.target_state,
            event=payload.event,
            profile=payload.profile,
            context=dict(payload.context),
            actor_user_id=user.id,
            correlation_id=payload.correlation_id,
        )
    except UnauthorizedProfileError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except PreconditionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except StateMachineError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except TransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return TransitionResponse(
        entity_type=result.entity_kind.value,
        entity_id=result.entity_id,
        from_state=result.from_state,
        to_state=result.to_state,
        event=result.event,
        auto_follow_up=result.auto_follow_up,
    )


@router.post(
    "/atendimentos/{atendimento_id}/transitions",
    response_model=TransitionResponse,
)
def transition_atendimento(
    atendimento_id: int,
    payload: TransitionRequest,
    current_user: User = Depends(require_permissions("work_order.status_change")),
    db: Session = Depends(get_db),
) -> TransitionResponse:
    return _dispatch(EntityKind.ATENDIMENTO, atendimento_id, payload, db, current_user)


@router.post(
    "/orcamentos/{orcamento_id}/transitions",
    response_model=TransitionResponse,
)
def transition_orcamento(
    orcamento_id: int,
    payload: TransitionRequest,
    current_user: User = Depends(require_permissions("estimate.approve")),
    db: Session = Depends(get_db),
) -> TransitionResponse:
    return _dispatch(EntityKind.ORCAMENTO, orcamento_id, payload, db, current_user)


@router.post(
    "/os/{os_id}/transitions",
    response_model=TransitionResponse,
)
def transition_os(
    os_id: int,
    payload: TransitionRequest,
    current_user: User = Depends(require_permissions("work_order.status_change")),
    db: Session = Depends(get_db),
) -> TransitionResponse:
    return _dispatch(EntityKind.OS, os_id, payload, db, current_user)


@router.get(
    "/{entity_kind}/{entity_id}/events",
    response_model=list[StateEventItem],
)
def list_events(
    entity_kind: EntityKind,
    entity_id: int,
    current_user: User = Depends(require_permissions("work_order.status_change")),
    db: Session = Depends(get_db),
) -> list[StateEventItem]:
    events = list_history(db, entity_kind=entity_kind, entity_id=entity_id)
    return [StateEventItem.model_validate(evt) for evt in events]
