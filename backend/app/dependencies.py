from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.db import ApiKey, Role, RolePermission, User
from app.services.auth_service import get_user_from_jwt

security = HTTPBearer(auto_error=False)


# ── User loader ─────────────────────────────────────────────────────────────

async def _load_user_with_roles(db: AsyncSession, user_id) -> User | None:
    """Wrapper around rbac_service._load_user_with_roles for backward refs."""
    from app.services.rbac_service import _load_user_with_roles as _loader
    return await _loader(db, user_id)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Зависимость для UI эндпоинтов: требует JWT токен.

    Eager-loads user.roles + role.permissions so that RBAC permission checks
    (`rbac_service.require_permission`) don't trigger lazy queries.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await get_user_from_jwt(db, credentials.credentials)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен недействителен или истёк",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Re-fetch with roles eager-loaded (get_user_from_jwt returns a plain User).
    return await _load_user_with_roles(db, user.id)


# ── SDK auth ────────────────────────────────────────────────────────────────

async def get_sdk_auth(
    x_api_key:     str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Зависимость для SDK эндпоинтов (/assignments, /events).

    Принимает:
      - `X-API-Key` (preferred for SDK) — checks the key is active and the
        owner is active. Scope enforcement happens at the router level via
        `require_sdk_scope`.
      - `Authorization: Bearer <jwt>` — falls back to JWT for users hitting
        SDK endpoints directly (debugging / manual testing).

    Scope check is NOT here — it's a separate dependency
    (`require_sdk_scope("events:write")`) so each endpoint can declare its
    own required scope. Keys with `scopes == ["*"]` are treated as having
    every scope (admin SDK keys).
    """
    from sqlalchemy import select

    if x_api_key:
        result = await db.execute(
            select(ApiKey)
            .options(selectinload(ApiKey.user).selectinload(User.roles).selectinload(Role.permissions))
            .where(ApiKey.key == x_api_key, ApiKey.is_active == True)
        )
        api_key = result.scalar_one_or_none()
        if api_key and api_key.user and api_key.user.is_active:
            # Touch last_used_at (auth_service also does this; keeping the
            # SDK path self-contained for clarity).
            from datetime import datetime
            if (
                api_key.last_used_at is None
                or (datetime.utcnow() - api_key.last_used_at).total_seconds() > 3600
            ):
                api_key.last_used_at = datetime.utcnow()
            return api_key.user

    if authorization and authorization.startswith("Bearer "):
        user = await get_user_from_jwt(db, authorization[7:])
        if user and user.is_active:
            return await _load_user_with_roles(db, user.id)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Требуется X-API-Key или Bearer токен",
    )


def require_sdk_scope(scope: str):
    """
    FastAPI dependency that ensures the calling SDK key carries `scope`.

    Uses the X-API-Key lookup directly (does NOT depend on `get_sdk_auth`,
    because that one accepts JWT fallback and JWTs don't carry scopes).

    Used by SDK endpoints:
        @router.post("/events", dependencies=[Depends(require_sdk_scope("events:write"))])
    """
    from sqlalchemy import select

    async def _checker(
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        authorization: str | None = Header(default=None),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if x_api_key:
            result = await db.execute(
                select(ApiKey)
                .options(selectinload(ApiKey.user).selectinload(User.roles).selectinload(Role.permissions))
                .where(ApiKey.key == x_api_key, ApiKey.is_active == True)
            )
            api_key = result.scalar_one_or_none()
            if not api_key or not api_key.user or not api_key.user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Невалидный или отозванный API ключ",
                )
            scopes = api_key.scopes or []
            if "*" in scopes or scope in scopes:
                return api_key.user
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API ключ не имеет scope «{scope}»",
            )

        # JWT fallback: user-level access is enough; SDK endpoints are still
        # usable from the UI for debugging.
        if authorization and authorization.startswith("Bearer "):
            user = await get_user_from_jwt(db, authorization[7:])
            if user and user.is_active:
                return await _load_user_with_roles(db, user.id)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется X-API-Key с подходящим scope",
        )

    return _checker