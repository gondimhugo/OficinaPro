import unittest

from backend.state_transitions import (
    PreconditionError,
    TransitionError,
    UnauthorizedProfileError,
    budget_validator,
    os_validator,
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
            context={"budget_approved": True},
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


if __name__ == "__main__":
    unittest.main()
