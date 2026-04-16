from datetime import datetime, timedelta, timezone
import unittest

from backend.audit import (
    AuditPermissionError,
    AuditQuery,
    ImmutableAuditLogStore,
    RetentionPolicy,
    build_audit_event,
)


class AuditStoreTests(unittest.TestCase):
    def test_rejects_business_user_write(self):
        store = ImmutableAuditLogStore()
        event = build_audit_event(
            {
                "actor_id": "u1",
                "actor_role": "financeiro",
                "resource_type": "OS",
                "resource_id": "OS-1",
                "action": "mudanca_status_os",
                "before": {"state": "ABERTA"},
                "after": {"state": "EM_EXECUCAO"},
                "timestamp_utc": datetime.now(timezone.utc),
                "ip_address": "127.0.0.1",
                "device_id": "dev-1",
                "correlation_id": "corr-1",
                "metadata": {"os_id": "OS-1"},
            }
        )

        with self.assertRaises(AuditPermissionError):
            store.append(event, principal_type="business_user")

    def test_supports_query_by_os_user_and_period(self):
        store = ImmutableAuditLogStore(retention_policy=RetentionPolicy(retention_days=30))
        now = datetime.now(timezone.utc)
        event = build_audit_event(
            {
                "actor_id": "u2",
                "actor_role": "supervisor",
                "resource_type": "OS",
                "resource_id": "OS-99",
                "action": "mudanca_status_os",
                "before": {"state": "ABERTA"},
                "after": {"state": "EM_EXECUCAO"},
                "timestamp_utc": now,
                "ip_address": "10.0.0.1",
                "device_id": "tablet-22",
                "correlation_id": "req-abc",
                "metadata": {"os_id": "OS-99"},
            }
        )
        store.append(event, principal_type="service")

        filtered = store.query(
            AuditQuery(
                os_id="OS-99",
                user_id="u2",
                start_utc=now - timedelta(seconds=1),
                end_utc=now + timedelta(seconds=1),
            )
        )
        self.assertEqual(len(filtered), 1)


if __name__ == "__main__":
    unittest.main()
