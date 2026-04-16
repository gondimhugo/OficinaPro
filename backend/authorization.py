"""Autorização híbrida RBAC + ABAC com reason codes padronizados."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Mapping, Optional, Sequence, Set

Action = str
Resource = str
Scope = str


@dataclass(frozen=True)
class UserIdentity:
    user_id: str
    roles: Set[str]
    allowed_units: Set[str]
    approval_limit: float = 0.0
    manager_approval_limit: float = 0.0
    is_global_admin: bool = False


@dataclass(frozen=True)
class ResourceContext:
    owner_id: Optional[str]
    responsible_id: Optional[str]
    unit_id: Optional[str]
    value: float = 0.0
    status: str = "RASCUNHO"
    created_at_utc: Optional[datetime] = None
    creator_id: Optional[str] = None


@dataclass(frozen=True)
class AuthorizationDecision:
    allow: bool
    reason_code: str
    obligations: Mapping[str, object] = field(default_factory=dict)


ROLE_PERMISSIONS: Mapping[str, Mapping[Resource, Mapping[Action, Scope]]] = {
    "atendente": {
        "orcamento": {"criar": "proprio", "visualizar": "unidade"},
        "foto": {"criar": "proprio", "cancelar": "proprio", "visualizar": "unidade"},
    },
    "consultor_comercial": {
        "orcamento": {
            "criar": "unidade",
            "aprovar": "unidade",
            "editar_valor": "unidade",
            "cancelar": "unidade",
            "visualizar": "unidade",
        },
    },
    "tecnico": {
        "os": {
            "criar": "proprio",
            "aprovar": "proprio",
            "cancelar": "proprio",
            "visualizar": "unidade",
        },
    },
    "comprador": {
        "compra": {
            "criar": "unidade",
            "aprovar": "unidade",
            "editar_valor": "unidade",
            "cancelar": "unidade",
            "visualizar": "unidade",
        },
    },
    "financeiro": {
        "lancamento_financeiro": {
            "criar": "unidade",
            "aprovar": "unidade",
            "editar_valor": "unidade",
            "cancelar": "unidade",
            "estornar": "unidade",
            "visualizar": "unidade",
        },
    },
    "gerente_unidade": {
        "orcamento": {
            "criar": "unidade",
            "aprovar": "unidade",
            "editar_valor": "unidade",
            "cancelar": "unidade",
            "visualizar": "unidade",
        },
        "os": {
            "criar": "unidade",
            "aprovar": "unidade",
            "cancelar": "unidade",
            "visualizar": "unidade",
        },
        "compra": {
            "criar": "unidade",
            "aprovar": "unidade",
            "editar_valor": "unidade",
            "cancelar": "unidade",
            "visualizar": "unidade",
        },
        "lancamento_financeiro": {
            "criar": "unidade",
            "aprovar": "unidade",
            "editar_valor": "unidade",
            "cancelar": "unidade",
            "estornar": "unidade",
            "visualizar": "unidade",
        },
    },
    "admin_global": {
        "orcamento": {
            "criar": "global",
            "aprovar": "global",
            "editar_valor": "global",
            "cancelar": "global",
            "estornar": "global",
            "visualizar": "global",
        },
        "os": {
            "criar": "global",
            "aprovar": "global",
            "cancelar": "global",
            "estornar": "global",
            "visualizar": "global",
        },
        "compra": {
            "criar": "global",
            "aprovar": "global",
            "editar_valor": "global",
            "cancelar": "global",
            "estornar": "global",
            "visualizar": "global",
        },
        "lancamento_financeiro": {
            "criar": "global",
            "aprovar": "global",
            "editar_valor": "global",
            "cancelar": "global",
            "estornar": "global",
            "visualizar": "global",
        },
        "foto": {
            "criar": "global",
            "cancelar": "global",
            "visualizar": "global",
        },
    },
}


class AuthorizationService:
    """Pipeline único de autorização: RBAC, escopo e ABAC."""

    def authorize(
        self,
        *,
        user: UserIdentity,
        action: Action,
        resource: Resource,
        resource_context: ResourceContext,
        now_utc: Optional[datetime] = None,
        cancel_window_hours: int = 24,
    ) -> AuthorizationDecision:
        if not self._is_allowed_by_role(user=user, action=action, resource=resource):
            return AuthorizationDecision(False, "AUTH_DENY_ROLE")

        scope = self._scope_for(user=user, action=action, resource=resource)
        if not self._is_allowed_by_scope(user=user, scope=scope, context=resource_context):
            return AuthorizationDecision(False, "AUTH_DENY_SCOPE")

        abac_denial = self._evaluate_abac(
            user=user,
            action=action,
            context=resource_context,
            now_utc=now_utc,
            cancel_window_hours=cancel_window_hours,
        )
        if abac_denial:
            return abac_denial

        return AuthorizationDecision(True, "AUTH_ALLOW")

    @staticmethod
    def _is_allowed_by_role(*, user: UserIdentity, action: Action, resource: Resource) -> bool:
        for role in user.roles:
            permissions = ROLE_PERMISSIONS.get(role, {})
            if action in permissions.get(resource, {}):
                return True
        return False

    @staticmethod
    def _scope_for(*, user: UserIdentity, action: Action, resource: Resource) -> Scope:
        scopes: Set[Scope] = set()
        for role in user.roles:
            role_permissions = ROLE_PERMISSIONS.get(role, {})
            scope = role_permissions.get(resource, {}).get(action)
            if scope:
                scopes.add(scope)

        if "global" in scopes or user.is_global_admin:
            return "global"
        if "unidade" in scopes:
            return "unidade"
        return "proprio"

    @staticmethod
    def _is_allowed_by_scope(*, user: UserIdentity, scope: Scope, context: ResourceContext) -> bool:
        if scope == "global":
            return True
        if scope == "unidade":
            return bool(context.unit_id and context.unit_id in user.allowed_units)

        return bool(
            user.user_id in {context.owner_id, context.responsible_id}
            or (context.creator_id and context.creator_id == user.user_id)
        )

    def _evaluate_abac(
        self,
        *,
        user: UserIdentity,
        action: Action,
        context: ResourceContext,
        now_utc: Optional[datetime],
        cancel_window_hours: int,
    ) -> Optional[AuthorizationDecision]:
        now = now_utc or datetime.now(timezone.utc)

        if context.status in {"CANCELADO", "ESTORNADO", "FECHADO"} and action != "visualizar":
            return AuthorizationDecision(False, "AUTH_DENY_STATUS")

        if action == "aprovar":
            if context.creator_id and context.creator_id == user.user_id:
                return AuthorizationDecision(False, "AUTH_DENY_SOD")
            if context.value > user.approval_limit and "gerente_unidade" not in user.roles and not user.is_global_admin:
                return AuthorizationDecision(False, "AUTH_DENY_LIMIT")
            if (
                context.value > user.manager_approval_limit
                and "admin_global" not in user.roles
                and not user.is_global_admin
            ):
                return AuthorizationDecision(False, "AUTH_DENY_LIMIT")

        if action in {"cancelar", "estornar"} and context.created_at_utc:
            if now - context.created_at_utc > timedelta(hours=cancel_window_hours):
                if not ({"gerente_unidade", "admin_global"} & user.roles or user.is_global_admin):
                    return AuthorizationDecision(False, "AUTH_DENY_TIME_WINDOW")
                return AuthorizationDecision(
                    True,
                    "AUTH_ALLOW",
                    obligations={"requires_justification": True},
                )

        if action == "editar_valor" and context.status == "APROVADO":
            return AuthorizationDecision(
                True,
                "AUTH_ALLOW",
                obligations={
                    "requires_reopen_reason": True,
                    "requires_new_approval_flow": True,
                },
            )

        return None
