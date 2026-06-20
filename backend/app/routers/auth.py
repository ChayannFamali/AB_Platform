from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.db import User
from app.schemas.auth import (
    ApiKeyCreate,
    ApiKeyListItem,
    ApiKeyResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services import rbac_service
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_api_key,
    create_user,
    get_user_by_email,
    list_api_keys,
    revoke_api_key,
)

router = APIRouter()


# ── Auth ────────────────────────────────────────────────────────────────────

@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Регистрация. Первый пользователь → admin role; остальные → viewer role.
    """
    if await get_user_by_email(db, data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует",
        )
    user = await create_user(db, data.username, data.email, data.password)
    # Eager-load roles for the response.
    user = await rbac_service._load_user_with_roles(db, user.id)
    return UserResponse.model_validate(user)


@router.post("/auth/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Вход. Возвращает JWT токен (24 часа)."""
    user = await authenticate_user(db, data.email, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )
    token = create_access_token(str(user.id), user.email)
    user = await rbac_service._load_user_with_roles(db, user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Информация о текущем пользователе (включая роли и права)."""
    return UserResponse.model_validate(current_user)


# ── API Keys ────────────────────────────────────────────────────────────────
#
# Listing/revoking your own keys: any authenticated user (uses get_current_user).
# Creating a key: any authenticated user. (No admin gate — users can issue
# their own SDK keys for their own integrations.)

@router.post("/api-keys", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    data: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Создаёт SDK ключ. Полный ключ показывается ТОЛЬКО здесь — сохрани его."""
    key = await create_api_key(
        db, current_user.id, data.name, scopes=data.scopes,
    )
    return ApiKeyResponse.model_validate(key)


@router.get("/api-keys", response_model=list[ApiKeyListItem])
async def get_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Список ключей текущего пользователя (замаскированные)."""
    keys = await list_api_keys(db, current_user.id)
    return [ApiKeyListItem.from_key(k) for k in keys]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Отзывает ключ. Необратимо."""
    if not await revoke_api_key(db, key_id, current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ключ не найден")