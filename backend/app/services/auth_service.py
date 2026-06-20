"""
Auth сервис: хэширование паролей, JWT, CRUD пользователей и API ключей.

Хэширование: PBKDF2-HMAC-SHA256, 260 000 итераций (NIST SP 800-132).
Только stdlib — никаких новых зависимостей.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.db import ApiKey, Role, User, UserRole
from app.schemas.auth import DEFAULT_API_KEY_SCOPES

_PBKDF2_ITERATIONS = 260_000
_JWT_ALGORITHM     = "HS256"
_JWT_TTL_HOURS     = 24


# Password

def hash_password(password: str) -> str:
    salt = secrets.token_hex(32)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS
    )
    return f"pbkdf2:sha256:{_PBKDF2_ITERATIONS}:{salt}:{dk.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    try:
        _, algo, iters, salt, dk_hex = hashed.split(":", 4)
        dk = hashlib.pbkdf2_hmac(algo, plain.encode(), salt.encode(), int(iters))
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


# JWT

def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub":   str(user_id),
        "email": email,
        "iat":   datetime.now(timezone.utc),
        "exp":   datetime.now(timezone.utc) + timedelta(hours=_JWT_TTL_HOURS),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[_JWT_ALGORITHM])


# User CRUD

async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.email == email.lower())
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id) -> User | None:
    """Lightweight loader — roles NOT eager-loaded (used for token decode)."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession, username: str, email: str, password: str
) -> User:
    """
    Создать пользователя.

    Первый зарегистрированный пользователь получает роль `admin` (через RBAC);
    все последующие — роль `viewer` (safe default). Колонка `is_admin` также
    выставляется для обратной совместимости, но авторитетный источник —
    RBAC-роли.
    """
    count = await db.execute(select(func.count(User.id)))
    is_first = (count.scalar() or 0) == 0

    user = User(
        username=username,
        email=email.lower(),
        hashed_password=hash_password(password),
        is_admin=is_first,           # legacy — deprecated, kept for compat
    )
    db.add(user)
    await db.flush()

    # Assign RBAC role.
    role_key = "admin" if is_first else "viewer"
    role_result = await db.execute(select(Role).where(Role.key == role_key))
    role = role_result.scalar_one_or_none()
    if role is None:
        # Defense-in-depth: roles are seeded by migration 0006. If missing,
        # the platform is in an inconsistent state — surface a clear error.
        raise RuntimeError(
            f"Role «{role_key}» not seeded. Run alembic upgrade head."
        )
    db.add(UserRole(user_id=user.id, role_id=role.id))
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> User | None:
    user = await get_user_by_email(db, email)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def get_user_from_jwt(db: AsyncSession, token: str) -> User | None:
    """
    Decode JWT and return the user (without roles — caller decides whether
    to re-fetch with roles eager-loaded).
    """
    try:
        payload = _decode_token(token)
        return await get_user_by_id(db, UUID(payload["sub"]))
    except Exception:
        return None


# API Keys

def _generate_key() -> str:
    """abp_<64 hex символа> — легко опознать как AB Platform ключ."""
    return f"abp_{secrets.token_hex(32)}"


async def create_api_key(
    db: AsyncSession,
    user_id: UUID,
    name: str,
    scopes: list[str] | None = None,
) -> ApiKey:
    """
    Create an API key.

    `scopes=None` → falls back to DEFAULT_API_KEY_SCOPES
    (`['assignments:read', 'events:write']`) to preserve SDK v0.1.0
    backward compatibility.
    """
    effective_scopes = list(scopes) if scopes else list(DEFAULT_API_KEY_SCOPES)
    key = ApiKey(
        user_id=user_id,
        name=name,
        key=_generate_key(),
        scopes=effective_scopes,
    )
    db.add(key)
    await db.flush()
    await db.refresh(key)
    return key


async def list_api_keys(db: AsyncSession, user_id: UUID) -> list[ApiKey]:
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user_id)
        .order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_api_key(db: AsyncSession, key_id: UUID, user_id: UUID) -> bool:
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id)
    )
    key = result.scalar_one_or_none()
    if not key:
        return False
    key.is_active = False
    return True


async def verify_api_key(db: AsyncSession, raw_key: str) -> User | None:
    """
    Проверяет API ключ → возвращает пользователя (с eager-loaded roles).

    last_used_at обновляется не чаще раза в час (не замедляем SDK запросы).

    NOTE: this helper returns the user for callers that don't need scope
    enforcement (e.g. status checks). Endpoints that need scope checks should
    use `dependencies.require_sdk_scope(...)` instead.
    """
    result = await db.execute(
        select(ApiKey)
        .options(selectinload(ApiKey.user).selectinload(User.roles).selectinload(Role.permissions))
        .where(ApiKey.key == raw_key, ApiKey.is_active == True)
    )
    api_key = result.scalar_one_or_none()
    if not api_key or not api_key.user or not api_key.user.is_active:
        return None

    if (
        api_key.last_used_at is None
        or (datetime.utcnow() - api_key.last_used_at).total_seconds() > 3600
    ):
        api_key.last_used_at = datetime.utcnow()

    return api_key.user