from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Oficina Pro API"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/oficina_pro"
    jwt_secret_key: str = "change-me-in-production-at-least-32-bytes-long"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    forgot_password_expire_minutes: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
