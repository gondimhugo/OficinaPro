from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permissions
from app.db.deps import get_db
from app.models.entities import User
from app.schemas.audit import AttachmentAuditRequest, ChangeStatusRequest, CriticalActionRequest
from app.schemas.auth import MessageResponse
from app.services.audit import register_audit

router = APIRouter(prefix="/critical-actions", tags=["audit"])


@router.post("/value-change", response_model=MessageResponse)
def audit_value_change(
    payload: CriticalActionRequest,
    current_user: User = Depends(require_permissions("finance.value_change")),
    db: Session = Depends(get_db),
) -> MessageResponse:
    register_audit(
        db,
        actor_user_id=current_user.id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        action="value.change",
        payload=payload.payload,
    )
    return MessageResponse(detail="Alteração de valor auditada")


@router.post("/approval-decision", response_model=MessageResponse)
def audit_approval_decision(
    payload: CriticalActionRequest,
    current_user: User = Depends(
        require_permissions("estimate.approve", "purchase.approve")
    ),
    db: Session = Depends(get_db),
) -> MessageResponse:
    register_audit(
        db,
        actor_user_id=current_user.id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        action="approval.decision",
        payload=payload.payload,
    )
    return MessageResponse(detail="Aprovação/Rejeição auditada")


@router.post("/cash-close", response_model=MessageResponse)
def audit_cash_close(
    payload: CriticalActionRequest,
    current_user: User = Depends(require_permissions("cash.close")),
    db: Session = Depends(get_db),
) -> MessageResponse:
    register_audit(
        db,
        actor_user_id=current_user.id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        action="cash.close",
        payload=payload.payload,
    )
    return MessageResponse(detail="Fechamento de caixa auditado")


@router.post("/work-order-status", response_model=MessageResponse)
def audit_work_order_status(
    payload: ChangeStatusRequest,
    current_user: User = Depends(require_permissions("work_order.status_change")),
    db: Session = Depends(get_db),
) -> MessageResponse:
    body = payload.payload or {}
    body["new_status"] = payload.new_status
    register_audit(
        db,
        actor_user_id=current_user.id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        action="work_order.status_change",
        payload=body,
    )
    return MessageResponse(detail="Mudança de status de OS auditada")


@router.post("/photo-event", response_model=MessageResponse)
def audit_photo_event(
    payload: AttachmentAuditRequest,
    current_user: User = Depends(require_permissions("attachment.manage")),
    db: Session = Depends(get_db),
) -> MessageResponse:
    action = "attachment.upload" if payload.operation == "upload" else "attachment.remove"
    register_audit(
        db,
        actor_user_id=current_user.id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        action=action,
        payload=payload.payload,
    )
    return MessageResponse(detail="Evento de foto auditado")
