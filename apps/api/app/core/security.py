from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt

from app.core.config import settings


def _utc_now() -> datetime:
    return datetime.now(UTC)


def hash_password(password: str, *, iterations: int = 600_000) -> str:
    salt = secrets.token_bytes(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${pwd_hash.hex()}"


def verify_password(plain_password: str, stored_password_hash: str | None) -> bool:
    if not stored_password_hash:
        return False
    try:
        algorithm, iter_s, salt_hex, expected_hash_hex = stored_password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iter_s)
    except (TypeError, ValueError):
        return False

    computed = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        iterations,
    ).hex()
    return hmac.compare_digest(computed, expected_hash_hex)


def _encode_token(payload: dict[str, Any], expires_delta: timedelta) -> str:
    now = _utc_now()
    claims = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str) -> str:
    return _encode_token(
        {"sub": subject, "type": "access", "jti": uuid4().hex},
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(subject: str) -> tuple[str, str, datetime]:
    expires_at = _utc_now() + timedelta(days=settings.refresh_token_expire_days)
    jti = uuid4().hex
    token = _encode_token(
        {"sub": subject, "type": "refresh", "jti": jti},
        timedelta(days=settings.refresh_token_expire_days),
    )
    return token, jti, expires_at


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def generate_password_reset_token() -> str:
    return secrets.token_urlsafe(48)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
