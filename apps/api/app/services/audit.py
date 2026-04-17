from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.entities import AuditLog

CRITICAL_AUDIT_ACTIONS = {
    "value.change",
    "approval.decision",
    "cash.close",
    "work_order.status_change",
    "attachment.upload",
    "attachment.remove",
}


def register_audit(
    db: Session,
    *,
    actor_user_id: int,
    entity_type: str,
    entity_id: int,
    action: str,
    payload: dict | None = None,
) -> AuditLog:
    if action not in CRITICAL_AUDIT_ACTIONS:
        raise ValueError(f"Ação crítica não suportada para auditoria: {action}")

    item = AuditLog(
        actor_user_id=actor_user_id,
        created_by=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        payload=json.dumps(payload or {}, ensure_ascii=False),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
