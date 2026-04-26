from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db import User
from app.services.auth_service import get_user_from_jwt, verify_api_key

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Зависимость для UI эндпоинтов: требует JWT токен."""
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
    return user


async def get_sdk_auth(
    x_api_key:     str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Зависимость для SDK эндпоинтов (/assignments, /events).
    Принимает API ключ (X-API-Key) или JWT (Authorization: Bearer).
    """
    if x_api_key:
        user = await verify_api_key(db, x_api_key)
        if user:
            return user

    if authorization and authorization.startswith("Bearer "):
        user = await get_user_from_jwt(db, authorization[7:])
        if user and user.is_active:
            return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Требуется X-API-Key или Bearer токен",
    )
