from datetime import datetime, timedelta, timezone
import unittest

from backend.portal_security import (
    AuthorizationError,
    InvalidExternalIdError,
    PortalRepository,
    TemporaryURLSigner,
)


class PortalOwnershipTests(unittest.TestCase):
    def test_list_returns_only_resources_from_requesting_client(self):
        repository = PortalRepository()
        repository.create_resource(client_id="cliente-a", resource_type="os", payload={"title": "A"})
        repository.create_resource(client_id="cliente-b", resource_type="os", payload={"title": "B"})
        repository.create_resource(client_id="cliente-a", resource_type="documento", payload={"title": "Doc"})

        resources = repository.list_resources_for_client(client_id="cliente-a")

        self.assertEqual(len(resources), 2)
        self.assertTrue(all(resource.client_id == "cliente-a" for resource in resources))

    def test_blocks_cross_client_access_for_direct_lookup(self):
        repository = PortalRepository()
        resource = repository.create_resource(client_id="cliente-a", resource_type="foto", payload={})

        with self.assertRaises(AuthorizationError):
            repository.get_resource_for_client(client_id="cliente-b", external_id=resource.external_id)

    def test_enforces_non_sequential_external_id(self):
        repository = PortalRepository()

        with self.assertRaises(InvalidExternalIdError):
            repository.create_resource(
                client_id="cliente-a",
                resource_type="os",
                payload={},
                external_id="123",
            )

    def test_generates_uuid_external_ids_by_default(self):
        repository = PortalRepository()

        resource = repository.create_resource(client_id="cliente-a", resource_type="os", payload={})

        self.assertRegex(resource.external_id, r"^[0-9a-f\-]{36}$")


class TemporaryMediaURLTests(unittest.TestCase):
    def test_signed_url_is_client_bound_and_temporary(self):
        signer = TemporaryURLSigner(secret_key="segredo")
        now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)

        url = signer.generate_url(
            object_key="docs/contrato.pdf",
            client_id="cliente-a",
            expires_in=timedelta(minutes=5),
            now_utc=now,
        )

        self.assertTrue(signer.validate_url(signed_url=url, client_id="cliente-a", now_utc=now))
        self.assertFalse(
            signer.validate_url(
                signed_url=url,
                client_id="cliente-a",
                now_utc=now + timedelta(minutes=6),
            )
        )
        self.assertFalse(signer.validate_url(signed_url=url, client_id="cliente-b", now_utc=now))

    def test_rejects_tampered_signature(self):
        signer = TemporaryURLSigner(secret_key="segredo")
        now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
        url = signer.generate_url(
            object_key="fotos/veiculo.jpg",
            client_id="cliente-a",
            expires_in=timedelta(minutes=10),
            now_utc=now,
        )

        tampered = url.replace("veiculo.jpg", "outro.jpg")

        self.assertFalse(signer.validate_url(signed_url=tampered, client_id="cliente-a", now_utc=now))


if __name__ == "__main__":
    unittest.main()
