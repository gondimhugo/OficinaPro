from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Oficina Pro API"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/oficina_pro"
    jwt_secret_key: str = "change-me-in-production-at-least-32-bytes-long"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    forgot_password_expire_minutes: int = 30

    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        parsed = urlparse(value)
        scheme = parsed.scheme
        if scheme in {"postgres", "postgresql"}:
            scheme = "postgresql+psycopg"

        host = parsed.hostname or ""
        is_supabase = host.endswith(".supabase.co") or host.endswith(".supabase.com")
        query_pairs = dict(parse_qsl(parsed.query, keep_blank_values=True))
        if is_supabase and "sslmode" not in query_pairs:
            query_pairs["sslmode"] = "require"

        return urlunparse(parsed._replace(scheme=scheme, query=urlencode(query_pairs)))


settings = Settings()
