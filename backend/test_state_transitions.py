import unittest

from backend.audit import AuditError, ImmutableAuditLogStore


def _os_audit_context(**overrides):
    ctx = {
        "audit_store": ImmutableAuditLogStore(),
        "actor_id": "u-test",
        "resource_id": "OS-T",
        "os_id": "OS-T",
        "correlation_id": "corr",
        "ip_address": "127.0.0.1",
        "device_id": "dev",
    }
    ctx.update(overrides)
    return ctx
from backend.state_enums import AtendimentoState, OrcamentoState, OSState
from backend.state_transitions import (
    PreconditionError,
    ReconciliationError,
    TransitionError,
    UnauthorizedProfileError,
    atendimento_validator,
    auto_block_on_pending_part,
    budget_validator,
    orcamento_validator_v2,
    os_item_lifecycle_validator,
    os_validator,
    os_validator_v2,
    reconcile_inventory,
)


class BudgetValidatorTests(unittest.TestCase):
    def test_allows_valid_draft_to_sent_transition(self):
        validator = budget_validator()
        ctx = {"has_valid_items": True, "has_customer": True}

        result = validator.apply(
            current_state="RASCUNHO",
            target_state="ENVIADO",
            event="enviar_orcamento",
            profile="atendimento",
            context=ctx,
        )

        self.assertEqual(result["state"], "ENVIADO")
        self.assertTrue(result["portal_synced"])
        self.assertIn("queued", result["notifications"])
        self.assertGreaterEqual(len(result["history"]), 1)

    def test_blocks_transition_for_unauthorized_profile(self):
        validator = budget_validator()

        with self.assertRaises(UnauthorizedProfileError):
            validator.apply(
                current_state="ENVIADO",
                target_state="APROVADO",
                event="aprovar_orcamento",
                profile="tecnico",
                context={},
            )

    def test_blocks_conversion_without_approved_budget_flag(self):
        validator = budget_validator()

        with self.assertRaises(PreconditionError):
            validator.apply(
                current_state="APROVADO",
                target_state="CONVERTIDO",
                event="converter_em_os",
                profile="admin",
                context={"budget_approved": False},
            )


class OSValidatorTests(unittest.TestCase):
    def test_allows_open_to_execution_with_budget_approved(self):
        validator = os_validator()

        result = validator.apply(
            current_state="ABERTA",
            target_state="EM_EXECUCAO",
            event="iniciar_execucao",
            profile="supervisor",
            context={
                "budget_approved": True,
                "audit_store": ImmutableAuditLogStore(),
                "actor_id": "u-1",
                "os_id": "OS-1",
                "correlation_id": "req-1",
                "ip_address": "127.0.0.1",
                "device_id": "device-1",
            },
        )

        self.assertEqual(result["state"], "EM_EXECUCAO")
        self.assertTrue(result["portal_synced"])

    def test_blocks_non_mapped_transition(self):
        validator = os_validator()

        with self.assertRaises(TransitionError):
            validator.apply(
                current_state="ABERTA",
                target_state="ENCERRADA",
                event="encerrar_os",
                profile="admin",
                context={"budget_approved": True},
            )

    def test_requires_audit_for_sensitive_budget_approval(self):
        validator = budget_validator()

        with self.assertRaises(AuditError):
            validator.apply(
                current_state="ENVIADO",
                target_state="APROVADO",
                event="aprovar_orcamento",
                profile="admin",
                context={},
            )


class ItemLifecycleValidatorTests(unittest.TestCase):
    def test_reserve_requires_os_link_or_audited_exception(self):
        validator = os_item_lifecycle_validator()

        with self.assertRaises(PreconditionError):
            validator.apply(
                current_state="PREVISTO_ORCAMENTO",
                target_state="RESERVADO_OS",
                event="reservar_na_conversao_os",
                profile="planejador",
                context={"requested_qty": 3},
            )

    def test_allows_audited_exception_for_unlinked_consumption(self):
        validator = os_item_lifecycle_validator()
        ctx = {
            "allow_unlinked_consumption": True,
            "exception_audit_id": "AUD-778",
            "consumed_qty": 1,
            "step_id": "ETAPA-1",
            "audit_store": ImmutableAuditLogStore(),
            "actor_id": "tecnico-1",
            "resource_id": "item-OS-1",
            "os_id": None,
            "correlation_id": "corr-99",
            "ip_address": "127.0.0.1",
            "device_id": "coletor-1",
        }

        result = validator.apply(
            current_state="RESERVADO_OS",
            target_state="CONSUMO_REAL",
            event="baixar_consumo_etapa",
            profile="tecnico",
            context=ctx,
        )

        self.assertEqual(result["state"], "CONSUMO_REAL")
        self.assertEqual(result["step_consumptions"][0]["step_id"], "ETAPA-1")

    def test_reconciles_inventory_and_raises_on_divergence(self):
        result = reconcile_inventory(
            physical_balance=10,
            system_balance=8,
            consumed_total=2,
        )
        self.assertTrue(result["is_consistent"])

        with self.assertRaises(ReconciliationError):
            reconcile_inventory(
                physical_balance=10,
                system_balance=10,
                consumed_total=2,
            )


class AtendimentoValidatorTests(unittest.TestCase):
    def test_iniciar_avaliacao_requires_customer_and_complaint(self):
        validator = atendimento_validator()

        with self.assertRaises(PreconditionError):
            validator.apply(
                current_state=AtendimentoState.ABERTO.value,
                target_state=AtendimentoState.EM_AVALIACAO.value,
                event="iniciar_avaliacao",
                profile="atendimento",
                context={"has_customer": True},
            )

    def test_converter_em_orcamento_success(self):
        validator = atendimento_validator()

        result = validator.apply(
            current_state=AtendimentoState.EM_AVALIACAO.value,
            target_state=AtendimentoState.CONVERTIDO.value,
            event="converter_em_orcamento",
            profile="orcamentista",
            context={"diagnosis_completed": True},
        )

        self.assertEqual(result["state"], AtendimentoState.CONVERTIDO.value)
        self.assertTrue(result["orcamento_created"])

    def test_unauthorized_profile_blocked(self):
        validator = atendimento_validator()

        with self.assertRaises(UnauthorizedProfileError):
            validator.apply(
                current_state=AtendimentoState.ABERTO.value,
                target_state=AtendimentoState.CANCELADO.value,
                event="cancelar_atendimento",
                profile="tecnico",
                context={},
            )


class OSValidatorV2Tests(unittest.TestCase):
    def test_open_to_execution_requires_no_pending_parts(self):
        validator = os_validator_v2()

        with self.assertRaises(PreconditionError):
            validator.apply(
                current_state=OSState.ABERTA.value,
                target_state=OSState.EM_EXECUCAO.value,
                event="iniciar_execucao",
                profile="supervisor",
                context=_os_audit_context(
                    budget_approved=True, has_pending_parts=True
                ),
            )

    def test_auto_block_on_pending_part_transitions_to_bloqueada_peca(self):
        context = _os_audit_context(has_pending_parts=True)
        new_state = auto_block_on_pending_part(
            os_state=OSState.EM_EXECUCAO.value,
            context=context,
        )
        self.assertEqual(new_state, OSState.BLOQUEADA_PECA.value)
        self.assertEqual(context["state"], OSState.BLOQUEADA_PECA.value)

    def test_auto_block_is_noop_when_no_pending_parts(self):
        context = _os_audit_context(has_pending_parts=False)
        new_state = auto_block_on_pending_part(
            os_state=OSState.EM_EXECUCAO.value,
            context=context,
        )
        self.assertEqual(new_state, OSState.EM_EXECUCAO.value)

    def test_quality_approval_requires_checklist(self):
        validator = os_validator_v2()

        with self.assertRaises(PreconditionError):
            validator.apply(
                current_state=OSState.QUALIDADE.value,
                target_state=OSState.PRONTA_ENTREGA.value,
                event="aprovar_qualidade",
                profile="qualidade",
                context=_os_audit_context(),
            )

    def test_happy_path_aberta_to_encerrada(self):
        validator = os_validator_v2()
        context = _os_audit_context(
            budget_approved=True,
            has_pending_parts=False,
            quality_checklist_ok=True,
            delivery_confirmed=True,
            billing_closed=True,
        )

        validator.apply(
            current_state=OSState.ABERTA.value,
            target_state=OSState.EM_EXECUCAO.value,
            event="iniciar_execucao",
            profile="supervisor",
            context=context,
        )
        validator.apply(
            current_state=OSState.EM_EXECUCAO.value,
            target_state=OSState.QUALIDADE.value,
            event="enviar_para_qualidade",
            profile="supervisor",
            context=context,
        )
        validator.apply(
            current_state=OSState.QUALIDADE.value,
            target_state=OSState.PRONTA_ENTREGA.value,
            event="aprovar_qualidade",
            profile="qualidade",
            context=context,
        )
        validator.apply(
            current_state=OSState.PRONTA_ENTREGA.value,
            target_state=OSState.ENTREGUE.value,
            event="entregar_os",
            profile="atendimento",
            context=context,
        )
        result = validator.apply(
            current_state=OSState.ENTREGUE.value,
            target_state=OSState.ENCERRADA.value,
            event="encerrar_os",
            profile="financeiro",
            context=context,
        )
        self.assertEqual(result["state"], OSState.ENCERRADA.value)


class OrcamentoValidatorV2Tests(unittest.TestCase):
    def test_enum_values_match_validator_keys(self):
        validator = orcamento_validator_v2()
        expected_from = {
            OrcamentoState.RASCUNHO.value,
            OrcamentoState.ENVIADO.value,
            OrcamentoState.APROVADO.value,
        }
        actual_from = {key[0] for key in validator.rules}
        self.assertTrue(expected_from.issubset(actual_from))

    def test_invalid_transition_raises(self):
        validator = orcamento_validator_v2()
        with self.assertRaises(TransitionError):
            validator.apply(
                current_state=OrcamentoState.RASCUNHO.value,
                target_state=OrcamentoState.CONVERTIDO.value,
                event="converter_em_os",
                profile="admin",
                context={"budget_approved": True},
            )


if __name__ == "__main__":
    unittest.main()
