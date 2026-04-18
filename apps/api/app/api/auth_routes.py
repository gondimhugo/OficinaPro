from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_password_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from app.db.deps import get_db
from app.models.entities import PasswordResetToken, RefreshToken, User
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _now() -> datetime:
    return datetime.now(UTC)


def _is_expired(value: datetime) -> bool:
    current = _now()
    if value.tzinfo is None:
        current = current.replace(tzinfo=None)
    return value <= current


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )

    access_token = create_access_token(str(user.id))
    refresh_token, jti, expires_at = create_refresh_token(str(user.id))

    db.add(
        RefreshToken(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at,
            created_by=user.id,
        )
    )
    db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        decoded = decode_token(payload.refresh_token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido",
        ) from exc

    if decoded.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido",
        )

    user_id = int(decoded.get("sub"))
    jti = decoded.get("jti")
    token_row = db.scalar(select(RefreshToken).where(RefreshToken.jti == jti))
    user = db.get(User, user_id)

    if (
        not user
        or not user.is_active
        or not token_row
        or token_row.user_id != user_id
        or token_row.revoked_at is not None
        or _is_expired(token_row.expires_at)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido",
        )

    token_row.revoked_at = _now()
    access_token = create_access_token(str(user.id))
    new_refresh, new_jti, new_expires = create_refresh_token(str(user.id))
    db.add(
        RefreshToken(
            user_id=user.id,
            jti=new_jti,
            expires_at=new_expires,
            created_by=user.id,
        )
    )
    db.commit()

    return TokenResponse(access_token=access_token, refresh_token=new_refresh)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> ForgotPasswordResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))

    if user and user.is_active:
        raw_token = generate_password_reset_token()
        token_hash = hash_reset_token(raw_token)
        db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=_now() + timedelta(minutes=settings.forgot_password_expire_minutes),
                created_by=user.id,
            )
        )
        db.commit()

    return ForgotPasswordResponse(
        detail=("Se o e-mail existir, enviaremos um link de recuperação com validade limitada.")
    )


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    token_hash = hash_reset_token(payload.token)
    reset_row = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash)
        .where(PasswordResetToken.used_at.is_(None))
    )

    if not reset_row or _is_expired(reset_row.expires_at):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido ou expirado",
        )

    user = db.get(User, reset_row.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    user.password_hash = hash_password(payload.new_password)
    reset_row.used_at = _now()
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    db.commit()

    return MessageResponse(detail="Senha atualizada com sucesso")
