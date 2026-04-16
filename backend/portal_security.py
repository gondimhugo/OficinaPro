"""Segurança de ownership para consultas do portal e URLs temporárias."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from typing import Dict, List, Mapping, Optional
from urllib.parse import parse_qs, urlencode, urlparse
from uuid import UUID, uuid4


class AuthorizationError(PermissionError):
    """Erro para tentativas de acesso entre clientes diferentes."""


class ResourceNotFoundError(LookupError):
    """Recurso inexistente para o cliente solicitado."""


class InvalidExternalIdError(ValueError):
    """Identificador externo inválido (deve ser UUID)."""


@dataclass(frozen=True)
class PortalResource:
    internal_id: int
    external_id: str
    client_id: str
    resource_type: str
    payload: Mapping[str, object]


class PortalRepository:
    """Repositório com enforcement de ownership no backend."""

    def __init__(self) -> None:
        self._resources: Dict[str, PortalResource] = {}
        self._next_internal_id = 1

    def create_resource(
        self,
        *,
        client_id: str,
        resource_type: str,
        payload: Mapping[str, object],
        external_id: Optional[str] = None,
    ) -> PortalResource:
        ext_id = external_id or str(uuid4())
        self._validate_external_id(ext_id)

        resource = PortalResource(
            internal_id=self._next_internal_id,
            external_id=ext_id,
            client_id=client_id,
            resource_type=resource_type,
            payload=dict(payload),
        )
        self._resources[resource.external_id] = resource
        self._next_internal_id += 1
        return resource

    def list_resources_for_client(self, *, client_id: str, resource_type: Optional[str] = None) -> List[PortalResource]:
        resources = [resource for resource in self._resources.values() if resource.client_id == client_id]
        if resource_type:
            resources = [resource for resource in resources if resource.resource_type == resource_type]
        return resources

    def get_resource_for_client(self, *, client_id: str, external_id: str) -> PortalResource:
        self._validate_external_id(external_id)
        resource = self._resources.get(external_id)
        if resource is None:
            raise ResourceNotFoundError("Recurso não encontrado")
        if resource.client_id != client_id:
            raise AuthorizationError("Acesso negado: recurso pertence a outro cliente")
        return resource

    @staticmethod
    def _validate_external_id(external_id: str) -> None:
        try:
            UUID(external_id)
        except ValueError as exc:
            raise InvalidExternalIdError("ID externo deve ser UUID não sequencial") from exc


class TemporaryURLSigner:
    """Geração e validação de URLs assinadas e temporárias para mídia."""

    def __init__(self, *, secret_key: str, base_url: str = "https://portal.example.com/media") -> None:
        self._secret = secret_key.encode("utf-8")
        self._base_url = base_url.rstrip("/")

    def generate_url(
        self,
        *,
        object_key: str,
        client_id: str,
        expires_in: timedelta = timedelta(minutes=10),
        now_utc: Optional[datetime] = None,
    ) -> str:
        now = now_utc or datetime.now(timezone.utc)
        expires_at = int((now + expires_in).timestamp())
        signature = self._signature(object_key=object_key, client_id=client_id, expires_at=expires_at)

        query = urlencode(
            {
                "key": object_key,
                "client": client_id,
                "exp": str(expires_at),
                "sig": signature,
            }
        )
        return f"{self._base_url}?{query}"

    def validate_url(self, *, signed_url: str, client_id: str, now_utc: Optional[datetime] = None) -> bool:
        now = now_utc or datetime.now(timezone.utc)
        parsed = urlparse(signed_url)
        query = parse_qs(parsed.query)

        key = self._first(query, "key")
        url_client = self._first(query, "client")
        exp_value = self._first(query, "exp")
        sent_signature = self._first(query, "sig")
        if not key or not url_client or not exp_value or not sent_signature:
            return False

        if url_client != client_id:
            return False

        try:
            expires_at = int(exp_value)
        except ValueError:
            return False

        if now.timestamp() > expires_at:
            return False

        expected_signature = self._signature(object_key=key, client_id=url_client, expires_at=expires_at)
        return hmac.compare_digest(expected_signature, sent_signature)

    def _signature(self, *, object_key: str, client_id: str, expires_at: int) -> str:
        payload = f"{object_key}:{client_id}:{expires_at}".encode("utf-8")
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    @staticmethod
    def _first(values: Dict[str, List[str]], key: str) -> Optional[str]:
        items = values.get(key)
        if not items:
            return None
        return items[0]
