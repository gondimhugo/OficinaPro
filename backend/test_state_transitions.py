import unittest

from backend.audit import AuditError, ImmutableAuditLogStore
from backend.state_transitions import (
    PreconditionError,
    ReconciliationError,
    TransitionError,
    UnauthorizedProfileError,
    budget_validator,
    os_item_lifecycle_validator,
    os_validator,
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


if __name__ == "__main__":
    unittest.main()
