from datetime import datetime, timedelta, timezone
import unittest

from backend.authorization import AuthorizationService, ResourceContext, UserIdentity


class AuthorizationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = AuthorizationService()

    def test_denies_action_not_allowed_in_rbac(self):
        user = UserIdentity(
            user_id="u-atendimento",
            roles={"atendente"},
            allowed_units={"SP01"},
            approval_limit=1000,
            manager_approval_limit=10000,
        )
        context = ResourceContext(
            owner_id="u-atendimento",
            responsible_id=None,
            unit_id="SP01",
            status="RASCUNHO",
        )

        decision = self.service.authorize(
            user=user,
            action="aprovar",
            resource="os",
            resource_context=context,
        )

        self.assertFalse(decision.allow)
        self.assertEqual(decision.reason_code, "AUTH_DENY_ROLE")

    def test_denies_scope_for_different_unit(self):
        user = UserIdentity(
            user_id="u-comercial",
            roles={"consultor_comercial"},
            allowed_units={"SP01"},
            approval_limit=3000,
            manager_approval_limit=10000,
        )
        context = ResourceContext(
            owner_id="u-outro",
            responsible_id=None,
            unit_id="RJ01",
            status="RASCUNHO",
        )

        decision = self.service.authorize(
            user=user,
            action="visualizar",
            resource="orcamento",
            resource_context=context,
        )

        self.assertFalse(decision.allow)
        self.assertEqual(decision.reason_code, "AUTH_DENY_SCOPE")

    def test_denies_approval_above_limit_for_non_manager(self):
        user = UserIdentity(
            user_id="u-comercial",
            roles={"consultor_comercial"},
            allowed_units={"SP01"},
            approval_limit=2000,
            manager_approval_limit=5000,
        )
        context = ResourceContext(
            owner_id="u-comercial",
            responsible_id=None,
            creator_id="u-outro",
            unit_id="SP01",
            value=4500,
            status="ENVIADO",
        )

        decision = self.service.authorize(
            user=user,
            action="aprovar",
            resource="orcamento",
            resource_context=context,
        )

        self.assertFalse(decision.allow)
        self.assertEqual(decision.reason_code, "AUTH_DENY_LIMIT")

    def test_enforces_segregation_of_duties(self):
        user = UserIdentity(
            user_id="u-fin",
            roles={"financeiro"},
            allowed_units={"SP01"},
            approval_limit=3000,
            manager_approval_limit=10000,
        )
        context = ResourceContext(
            owner_id="u-fin",
            responsible_id=None,
            creator_id="u-fin",
            unit_id="SP01",
            value=1000,
            status="RASCUNHO",
        )

        decision = self.service.authorize(
            user=user,
            action="aprovar",
            resource="lancamento_financeiro",
            resource_context=context,
        )

        self.assertFalse(decision.allow)
        self.assertEqual(decision.reason_code, "AUTH_DENY_SOD")

    def test_cancel_after_window_requires_justification_obligation(self):
        now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
        user = UserIdentity(
            user_id="u-manager",
            roles={"gerente_unidade"},
            allowed_units={"SP01"},
            approval_limit=10000,
            manager_approval_limit=50000,
        )
        context = ResourceContext(
            owner_id="u-outro",
            responsible_id=None,
            creator_id="u-outro",
            unit_id="SP01",
            status="EM_EXECUCAO",
            created_at_utc=now - timedelta(hours=48),
        )

        decision = self.service.authorize(
            user=user,
            action="cancelar",
            resource="os",
            resource_context=context,
            now_utc=now,
            cancel_window_hours=24,
        )

        self.assertTrue(decision.allow)
        self.assertEqual(decision.reason_code, "AUTH_ALLOW")
        self.assertTrue(decision.obligations.get("requires_justification"))

    def test_edit_value_on_approved_resource_requires_reapproval_obligation(self):
        user = UserIdentity(
            user_id="u-manager",
            roles={"gerente_unidade"},
            allowed_units={"SP01"},
            approval_limit=10000,
            manager_approval_limit=50000,
        )
        context = ResourceContext(
            owner_id="u-manager",
            responsible_id=None,
            creator_id="u-other",
            unit_id="SP01",
            status="APROVADO",
        )

        decision = self.service.authorize(
            user=user,
            action="editar_valor",
            resource="orcamento",
            resource_context=context,
        )

        self.assertTrue(decision.allow)
        self.assertTrue(decision.obligations.get("requires_reopen_reason"))
        self.assertTrue(decision.obligations.get("requires_new_approval_flow"))


if __name__ == "__main__":
    unittest.main()
