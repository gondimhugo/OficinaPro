"""Validação central de transições de estado para Orçamento e OS."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, Mapping, MutableMapping, Sequence, Tuple

from backend.audit import (
    AuditError,
    ImmutableAuditLogStore,
    build_audit_event,
    map_transition_to_audit_action,
    should_require_audit,
)


class TransitionError(ValueError):
    """Erro para qualquer mudança de estado inválida."""


class UnauthorizedProfileError(TransitionError):
    """Perfil não autorizado para a transição."""


class PreconditionError(TransitionError):
    """Pré-condição não atendida."""


class ReconciliationError(TransitionError):
    """Divergências detectadas em reconciliação de estoque."""


Precondition = Callable[[Mapping[str, object]], bool]
Hook = Callable[[MutableMapping[str, object]], None]


@dataclass(frozen=True)
class TransitionRule:
    event: str
    allowed_profiles: Sequence[str]
    preconditions: Sequence[Precondition] = field(default_factory=tuple)
    postconditions: Sequence[Hook] = field(default_factory=tuple)
    side_effects: Sequence[Hook] = field(default_factory=tuple)


@dataclass
class TransitionValidator:
    entity_name: str
    rules: Dict[Tuple[str, str], TransitionRule]

    def apply(
        self,
        current_state: str,
        target_state: str,
        event: str,
        profile: str,
        context: MutableMapping[str, object],
    ) -> MutableMapping[str, object]:
        """Valida e aplica transição de estado de forma centralizada."""
        key = (current_state, target_state)
        rule = self.rules.get(key)
        if not rule:
            raise TransitionError(
                f"Transição inválida em {self.entity_name}: {current_state} -> {target_state}"
            )

        if rule.event != event:
            raise TransitionError(
                f"Evento inválido para {current_state} -> {target_state}. "
                f"Esperado: {rule.event}, recebido: {event}"
            )

        if profile not in set(rule.allowed_profiles):
            raise UnauthorizedProfileError(
                f"Perfil '{profile}' não autorizado para evento '{event}'"
            )

        failed = [pre for pre in rule.preconditions if not pre(context)]
        if failed:
            raise PreconditionError(
                f"{len(failed)} pré-condição(ões) não satisfeita(s) para '{event}'"
            )

        context["previous_state"] = current_state
        context["state"] = target_state
        self._append_audit(
            context,
            f"Transição {self.entity_name}: {current_state} -> {target_state} ({event})",
        )
        self._append_structured_audit(
            context=context,
            current_state=current_state,
            target_state=target_state,
            event=event,
            profile=profile,
        )

        for post in rule.postconditions:
            post(context)
        for effect in rule.side_effects:
            effect(context)

        return context

    def _append_structured_audit(
        self,
        context: MutableMapping[str, object],
        current_state: str,
        target_state: str,
        event: str,
        profile: str,
    ) -> None:
        action = map_transition_to_audit_action(self.entity_name, event)
        store = context.get("audit_store")
        if should_require_audit(action) and not isinstance(store, ImmutableAuditLogStore):
            raise AuditError(
                f"Ação sensível '{action}' exige audit_store imutável no contexto"
            )

        if not isinstance(store, ImmutableAuditLogStore):
            return

        payload = {
            "actor_id": context.get("actor_id", "desconhecido"),
            "actor_role": profile,
            "resource_type": self.entity_name,
            "resource_id": str(context.get("resource_id", context.get("os_id", "na"))),
            "action": action,
            "before": {"state": current_state},
            "after": {"state": target_state},
            "timestamp_utc": context.get("timestamp_utc", datetime.now(timezone.utc)),
            "ip_address": context.get("ip_address", "0.0.0.0"),
            "device_id": context.get("device_id", "desconhecido"),
            "correlation_id": context.get("correlation_id", "na"),
            "metadata": {
                "event": event,
                "os_id": context.get("os_id"),
            },
        }
        event_data = build_audit_event(payload)
        store.append(event_data, principal_type="system")

    @staticmethod
    def _append_audit(context: MutableMapping[str, object], message: str) -> None:
        history = context.setdefault("history", [])
        if isinstance(history, list):
            history.append(message)


def must_have_budget_approved(context: Mapping[str, object]) -> bool:
    return bool(context.get("budget_approved"))


def must_have_items_and_customer(context: Mapping[str, object]) -> bool:
    return bool(context.get("has_valid_items") and context.get("has_customer"))


def must_have_os_link_or_audited_exception(context: Mapping[str, object]) -> bool:
    if context.get("os_id"):
        return True
    return bool(context.get("allow_unlinked_consumption") and context.get("exception_audit_id"))


def must_have_available_balance_or_purchase_request(context: Mapping[str, object]) -> bool:
    requested_qty = int(context.get("requested_qty", 0))
    available_qty = int(context.get("available_qty", 0))
    purchase_request_id = context.get("purchase_request_id")
    return requested_qty <= available_qty or bool(purchase_request_id)


def must_have_received_and_inspected(context: Mapping[str, object]) -> bool:
    return bool(context.get("received_qty", 0) > 0 and context.get("inspection_ok"))


def mark_portal_sync(context: MutableMapping[str, object]) -> None:
    context["portal_synced"] = True


def mark_notification(context: MutableMapping[str, object]) -> None:
    notifications = context.setdefault("notifications", [])
    if isinstance(notifications, list):
        notifications.append("queued")


def mark_os_created(context: MutableMapping[str, object]) -> None:
    context["os_created"] = True


def reserve_item_quantity(context: MutableMapping[str, object]) -> None:
    requested_qty = int(context.get("requested_qty", 0))
    context["reserved_qty"] = requested_qty


def register_purchase_request(context: MutableMapping[str, object]) -> None:
    if context.get("purchase_request_id"):
        context["purchase_requested"] = True


def register_real_consumption(context: MutableMapping[str, object]) -> None:
    step_consumptions = context.setdefault("step_consumptions", [])
    if not isinstance(step_consumptions, list):
        step_consumptions = []
        context["step_consumptions"] = step_consumptions

    step_id = context.get("step_id", "etapa-nao-informada")
    consumed_qty = int(context.get("consumed_qty", 0))
    step_consumptions.append({"step_id": step_id, "consumed_qty": consumed_qty})


def budget_validator() -> TransitionValidator:
    rules: Dict[Tuple[str, str], TransitionRule] = {
        ("RASCUNHO", "ENVIADO"): TransitionRule(
            event="enviar_orcamento",
            allowed_profiles=("atendimento", "vendedor", "admin"),
            preconditions=(must_have_items_and_customer,),
            postconditions=(mark_notification,),
            side_effects=(mark_portal_sync,),
        ),
        ("ENVIADO", "APROVADO"): TransitionRule(
            event="aprovar_orcamento",
            allowed_profiles=("cliente", "atendimento", "admin"),
            side_effects=(mark_notification, mark_portal_sync),
        ),
        ("ENVIADO", "REJEITADO"): TransitionRule(
            event="rejeitar_orcamento",
            allowed_profiles=("cliente", "atendimento", "admin"),
            side_effects=(mark_notification, mark_portal_sync),
        ),
        ("ENVIADO", "EXPIRADO"): TransitionRule(
            event="expirar_orcamento",
            allowed_profiles=("sistema", "admin"),
            side_effects=(mark_notification, mark_portal_sync),
        ),
        ("APROVADO", "CONVERTIDO"): TransitionRule(
            event="converter_em_os",
            allowed_profiles=("atendimento", "planejador", "admin"),
            preconditions=(must_have_budget_approved,),
            postconditions=(mark_os_created,),
            side_effects=(mark_notification, mark_portal_sync),
        ),
    }
    return TransitionValidator(entity_name="Orçamento", rules=rules)


def os_validator() -> TransitionValidator:
    common_side_effects: Iterable[Hook] = (mark_notification, mark_portal_sync)

    rules: Dict[Tuple[str, str], TransitionRule] = {
        ("ABERTA", "EM_EXECUCAO"): TransitionRule(
            event="iniciar_execucao",
            allowed_profiles=("tecnico", "supervisor", "admin"),
            preconditions=(must_have_budget_approved,),
            side_effects=tuple(common_side_effects),
        ),
        ("ABERTA", "CANCELADA"): TransitionRule(
            event="cancelar_os",
            allowed_profiles=("supervisor", "admin"),
            side_effects=tuple(common_side_effects),
        ),
        ("EM_EXECUCAO", "BLOQUEADA"): TransitionRule(
            event="bloquear_os",
            allowed_profiles=("tecnico", "supervisor", "admin"),
            side_effects=tuple(common_side_effects),
        ),
        ("EM_EXECUCAO", "AGUARDANDO_PECA"): TransitionRule(
            event="aguardar_peca",
            allowed_profiles=("tecnico", "compras", "supervisor", "admin"),
            side_effects=tuple(common_side_effects),
        ),
        ("EM_EXECUCAO", "EM_QUALIDADE"): TransitionRule(
            event="enviar_para_qualidade",
            allowed_profiles=("tecnico", "supervisor", "admin"),
            side_effects=tuple(common_side_effects),
        ),
        ("EM_EXECUCAO", "CANCELADA"): TransitionRule(
            event="cancelar_os",
            allowed_profiles=("supervisor", "admin"),
            side_effects=tuple(common_side_effects),
        ),
        ("BLOQUEADA", "EM_EXECUCAO"): TransitionRule(
            event="desbloquear_os",
            allowed_profiles=("supervisor", "admin"),
            side_effects=tuple(common_side_effects),
        ),
        ("BLOQUEADA", "CANCELADA"): TransitionRule(
            event="cancelar_os",
            allowed_profiles=("supervisor", "admin"),
            side_effects=tuple(common_side_effects),
        ),
        ("AGUARDANDO_PECA", "EM_EXECUCAO"): TransitionRule(
            event="peca_recebida",
            allowed_profiles=("compras", "supervisor", "admin"),
            side_effects=tuple(common_side_effects),
        ),
        ("AGUARDANDO_PECA", "CANCELADA"): TransitionRule(
            event="cancelar_os",
            allowed_profiles=("supervisor", "admin"),
            side_effects=tuple(common_side_effects),
        ),
        ("EM_QUALIDADE", "PRONTA"): TransitionRule(
            event="aprovar_qualidade",
            allowed_profiles=("qualidade", "supervisor", "admin"),
            side_effects=tuple(common_side_effects),
        ),
        ("EM_QUALIDADE", "EM_EXECUCAO"): TransitionRule(
            event="reprovar_qualidade",
            allowed_profiles=("qualidade", "supervisor", "admin"),
            side_effects=tuple(common_side_effects),
        ),
        ("PRONTA", "ENTREGUE"): TransitionRule(
            event="entregar_os",
            allowed_profiles=("atendimento", "supervisor", "admin"),
            side_effects=tuple(common_side_effects),
        ),
        ("ENTREGUE", "ENCERRADA"): TransitionRule(
            event="encerrar_os",
            allowed_profiles=("atendimento", "financeiro", "admin"),
            side_effects=tuple(common_side_effects),
        ),
    }
    return TransitionValidator(entity_name="OS", rules=rules)


def os_item_lifecycle_validator() -> TransitionValidator:
    """Fluxo de materiais vinculados à OS: previsão, reserva, compra, recebimento e consumo."""

    rules: Dict[Tuple[str, str], TransitionRule] = {
        ("NAO_PLANEJADO", "PREVISTO_ORCAMENTO"): TransitionRule(
            event="prever_no_orcamento",
            allowed_profiles=("planejador", "orcamentista", "admin"),
        ),
        ("PREVISTO_ORCAMENTO", "RESERVADO_OS"): TransitionRule(
            event="reservar_na_conversao_os",
            allowed_profiles=("planejador", "estoque", "admin"),
            preconditions=(must_have_os_link_or_audited_exception,),
            postconditions=(reserve_item_quantity,),
        ),
        ("RESERVADO_OS", "REQUISICAO_COMPRA"): TransitionRule(
            event="gerar_requisicao_compra",
            allowed_profiles=("compras", "estoque", "admin"),
            preconditions=(must_have_available_balance_or_purchase_request,),
            postconditions=(register_purchase_request,),
        ),
        ("REQUISICAO_COMPRA", "RECEBIDO_CONFERIDO"): TransitionRule(
            event="receber_e_conferir",
            allowed_profiles=("almoxarife", "compras", "qualidade", "admin"),
            preconditions=(must_have_received_and_inspected,),
        ),
        ("RESERVADO_OS", "CONSUMO_REAL"): TransitionRule(
            event="baixar_consumo_etapa",
            allowed_profiles=("tecnico", "supervisor", "admin"),
            preconditions=(must_have_os_link_or_audited_exception,),
            postconditions=(register_real_consumption,),
        ),
        ("RECEBIDO_CONFERIDO", "CONSUMO_REAL"): TransitionRule(
            event="baixar_consumo_etapa",
            allowed_profiles=("tecnico", "supervisor", "admin"),
            preconditions=(must_have_os_link_or_audited_exception,),
            postconditions=(register_real_consumption,),
        ),
    }

    return TransitionValidator(entity_name="ItemOS", rules=rules)


def reconcile_inventory(
    *,
    physical_balance: int,
    system_balance: int,
    consumed_total: int,
    tolerance: int = 0,
) -> Dict[str, object]:
    """Reconcilia saldo físico, saldo no sistema e consumo apontado por etapa."""

    expected_system_balance = physical_balance - consumed_total
    delta = system_balance - expected_system_balance
    is_consistent = abs(delta) <= tolerance

    result: Dict[str, object] = {
        "physical_balance": physical_balance,
        "system_balance": system_balance,
        "consumed_total": consumed_total,
        "expected_system_balance": expected_system_balance,
        "delta": delta,
        "is_consistent": is_consistent,
    }

    if not is_consistent:
        raise ReconciliationError(
            "Reconciliação inconsistente: saldo físico, saldo sistema e consumo apontado divergem"
        )

    return result
