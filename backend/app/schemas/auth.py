import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

# Default scopes for new API keys (matches DB server_default — preserves
# backward compatibility with SDK v0.1.0).
DEFAULT_API_KEY_SCOPES: list[str] = ["assignments:read", "events:write"]


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


class RoleSummary(BaseModel):
    """Minimal role payload for embedding inside UserResponse."""
    id:   UUID
    key:  str
    name: str

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id:          UUID
    username:    str
    email:       str
    is_admin:    bool
    is_active:   bool
    created_at:  datetime
    # M-003: roles + flat permissions list (derived from all assigned roles).
    # `is_admin` is retained for backward compat with the v1 contract — the
    # authoritative check is now `roles[]` / `permissions[]`.
    roles:       list[RoleSummary]   = Field(default_factory=list)
    permissions: list[str]          = Field(default_factory=list)

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _derive_roles_and_permissions(cls, data):
        """
        When constructed from a User ORM object, `roles` and `permissions`
        live in the eager-loaded `roles[].permissions[].permission` chain,
        NOT on the User itself. Flatten them so the response includes both.

        Accepts either an ORM User or a dict (already-prepared payloads).
        """
        if hasattr(data, "roles"):
            roles = list(getattr(data, "roles", []) or [])
            role_summaries = [
                RoleSummary.model_validate(r) for r in roles
            ]
            perms: set[str] = set()
            for r in roles:
                for p in (getattr(r, "permissions", None) or []):
                    # ORM attribute is the RolePermission row; its string
                    # permission lives in `.permission`.
                    perm_value = getattr(p, "permission", None)
                    if perm_value is None and isinstance(p, str):
                        perm_value = p
                    if perm_value:
                        perms.add(perm_value)
            return {
                "id":           getattr(data, "id", None),
                "username":     getattr(data, "username", None),
                "email":        getattr(data, "email", None),
                "is_admin":     getattr(data, "is_admin", False),
                "is_active":    getattr(data, "is_active", True),
                "created_at":   getattr(data, "created_at", None),
                "roles":        role_summaries,
                "permissions":  sorted(perms),
            }
        return data


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserResponse


# API Keys

class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    scopes: list[str] | None = Field(
        default=None,
        description=(
            "Permission scopes. Defaults to "
            "['assignments:read', 'events:write'] when omitted. "
            "Use ['*'] to grant all SDK scopes."
        ),
    )


class ApiKeyResponse(BaseModel):
    """Полный ключ — только при создании. Больше не показывается."""
    id:           UUID
    name:         str
    key:          str
    scopes:       list[str]
    is_active:    bool
    created_at:   datetime
    last_used_at: datetime | None = None
    model_config = {"from_attributes": True}


class ApiKeyListItem(BaseModel):
    """Замаскированный ключ для списка: abp_a1b2c3d4e5f6***"""
    id:           UUID
    name:         str
    key_preview:  str
    scopes:       list[str]
    is_active:    bool
    created_at:   datetime
    last_used_at: datetime | None = None

    @classmethod
    def from_key(cls, key) -> "ApiKeyListItem":
        preview = key.key[:15] + "***" if len(key.key) > 15 else key.key
        return cls(
            id=key.id,
            name=key.name,
            key_preview=preview,
            scopes=key.scopes or [],
            is_active=key.is_active,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
        )