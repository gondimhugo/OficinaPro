from __future__ import annotations

from datetime import datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.deps import get_db
from app.models.entities import (
    Permission,
    RefreshToken,
    RolePermission,
    User,
    UserPermission,
    UserRole,
)

http_bearer = HTTPBearer(auto_error=False)


def _now() -> datetime:
    return datetime.utcnow()


def get_permission_codes(db: Session, user_id: int) -> set[str]:
    role_permission_query: Select[tuple[str]] = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id)
    )
    direct_permission_query: Select[tuple[str]] = (
        select(Permission.code)
        .join(UserPermission, UserPermission.permission_id == Permission.id)
        .where(UserPermission.user_id == user_id)
    )

    role_codes = {row[0] for row in db.execute(role_permission_query).all()}
    direct_codes = {row[0] for row in db.execute(direct_permission_query).all()}
    return role_codes | direct_codes


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    db: Session = Depends(get_db),
) -> User:
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token ausente")

    try:
        payload = decode_token(creds.credentials)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        ) from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    user_id = payload.get("sub")
    user = db.get(User, int(user_id)) if user_id else None
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inativo")

    return user


def get_current_user_with_permissions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> tuple[User, set[str]]:
    return user, get_permission_codes(db, user.id)


def require_permissions(*required_permissions: str):
    def _checker(
        user_ctx: tuple[User, set[str]] = Depends(get_current_user_with_permissions),
    ) -> User:
        user, permission_codes = user_ctx
        missing = [code for code in required_permissions if code not in permission_codes]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissões ausentes: {', '.join(missing)}",
            )
        return user

    return _checker


def revoke_refresh_token(db: Session, jti: str) -> None:
    token = db.scalar(select(RefreshToken).where(RefreshToken.jti == jti))
    if token and token.revoked_at is None:
        token.revoked_at = _now()
        db.add(token)
        db.commit()
