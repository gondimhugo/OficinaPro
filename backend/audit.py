"""Modelo de auditoria imutável para ações sensíveis de negócio."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence


class AuditError(ValueError):
    """Erro de validação para eventos de auditoria."""


class AuditPermissionError(PermissionError):
    """Ação não permitida no log de auditoria."""


@dataclass(frozen=True)
class AuditEvent:
    actor_id: str
    actor_role: str
    resource_type: str
    resource_id: str
    action: str
    before: Mapping[str, Any]
    after: Mapping[str, Any]
    timestamp_utc: datetime
    ip_address: str
    device_id: str
    correlation_id: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetentionPolicy:
    retention_days: int = 3650
    allow_legal_hold: bool = True


SENSITIVE_ACTIONS = {
    "aprovacao",
    "rejeicao",
    "alteracao_valor",
    "estorno",
    "fechamento_caixa",
    "mudanca_status_os",
    "upload_foto",
    "remocao_foto",
}


@dataclass
class AuditQuery:
    os_id: Optional[str] = None
    user_id: Optional[str] = None
    start_utc: Optional[datetime] = None
    end_utc: Optional[datetime] = None


class ImmutableAuditLogStore:
    """Store append-only com consulta por OS, usuário e período."""

    def __init__(self, retention_policy: RetentionPolicy | None = None) -> None:
        self._events: List[AuditEvent] = []
        self.retention_policy = retention_policy or RetentionPolicy()

    def append(self, event: AuditEvent, *, principal_type: str) -> None:
        if principal_type not in {"system", "service"}:
            raise AuditPermissionError(
                "Logs de auditoria não podem ser gravados diretamente por usuários de negócio"
            )
        self._events.append(event)

    def purge_expired(self, now_utc: datetime | None = None) -> int:
        now = now_utc or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=self.retention_policy.retention_days)
        original_size = len(self._events)
        self._events = [e for e in self._events if e.timestamp_utc >= cutoff]
        return original_size - len(self._events)

    def query(self, params: AuditQuery) -> Sequence[AuditEvent]:
        events: Iterable[AuditEvent] = self._events
        if params.os_id:
            events = (e for e in events if e.metadata.get("os_id") == params.os_id)
        if params.user_id:
            events = (e for e in events if e.actor_id == params.user_id)
        if params.start_utc:
            events = (e for e in events if e.timestamp_utc >= params.start_utc)
        if params.end_utc:
            events = (e for e in events if e.timestamp_utc <= params.end_utc)
        return list(events)

    def update(self, *_: Any, **__: Any) -> None:
        raise AuditPermissionError("Log de auditoria é imutável")

    def delete(self, *_: Any, **__: Any) -> None:
        raise AuditPermissionError("Log de auditoria é imutável")


def build_audit_event(payload: Mapping[str, Any]) -> AuditEvent:
    required_fields = (
        "actor_id",
        "actor_role",
        "resource_type",
        "resource_id",
        "action",
        "before",
        "after",
        "timestamp_utc",
        "ip_address",
        "device_id",
        "correlation_id",
    )
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise AuditError(f"Campos obrigatórios ausentes no evento de auditoria: {', '.join(missing)}")

    timestamp = payload["timestamp_utc"]
    if not isinstance(timestamp, datetime):
        raise AuditError("timestamp_utc deve ser datetime timezone-aware")
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise AuditError("timestamp_utc deve estar em UTC com timezone")

    return AuditEvent(
        actor_id=str(payload["actor_id"]),
        actor_role=str(payload["actor_role"]),
        resource_type=str(payload["resource_type"]),
        resource_id=str(payload["resource_id"]),
        action=str(payload["action"]),
        before=dict(payload["before"]),
        after=dict(payload["after"]),
        timestamp_utc=timestamp.astimezone(timezone.utc),
        ip_address=str(payload["ip_address"]),
        device_id=str(payload["device_id"]),
        correlation_id=str(payload["correlation_id"]),
        metadata=dict(payload.get("metadata", {})),
    )


def should_require_audit(action: str) -> bool:
    return action in SENSITIVE_ACTIONS


def map_transition_to_audit_action(entity_name: str, event: str) -> str:
    if entity_name == "OS":
        return "mudanca_status_os"
    if event == "aprovar_orcamento":
        return "aprovacao"
    if event == "rejeitar_orcamento":
        return "rejeicao"
    return "transicao_estado"
