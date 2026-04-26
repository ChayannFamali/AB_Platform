import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')


# Register / Login 

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=100)
    email:    str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError("Некорректный формат email")
        return v.lower()


class LoginRequest(BaseModel):
    email:    str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower()


class UserResponse(BaseModel):
    id:         UUID
    username:   str
    email:      str
    is_admin:   bool
    created_at: datetime
    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserResponse


# API Keys 

class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ApiKeyResponse(BaseModel):
    """Полный ключ — только при создании. Больше не показывается."""
    id:           UUID
    name:         str
    key:          str
    is_active:    bool
    created_at:   datetime
    last_used_at: datetime | None = None
    model_config = {"from_attributes": True}


class ApiKeyListItem(BaseModel):
    """Замаскированный ключ для списка: abp_a1b2c3d4e5f6***"""
    id:           UUID
    name:         str
    key_preview:  str
    is_active:    bool
    created_at:   datetime
    last_used_at: datetime | None = None

    @classmethod
    def from_key(cls, key) -> "ApiKeyListItem":
        preview = key.key[:15] + "***" if len(key.key) > 15 else key.key
        return cls(
            id=key.id, name=key.name, key_preview=preview,
            is_active=key.is_active, created_at=key.created_at,
            last_used_at=key.last_used_at,
        )
