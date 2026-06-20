"""
Pydantic schemas for RBAC (M-003, ADR-006).

Defines wire-format shapes for:
- Role CRUD (GET/POST/PATCH /api/v1/roles)
- User listing with their roles (GET /api/v1/users)
- Role assignment (POST /api/v1/users/{id}/roles)
- User activation toggle (PATCH /api/v1/users/{id})
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Roles ────────────────────────────────────────────────────────────────────

class RoleBase(BaseModel):
    key:         str = Field(..., min_length=1, max_length=50,
                             description="Stable identifier, e.g. 'admin'")
    name:        str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)


class RoleCreate(RoleBase):
    permissions: list[str] = Field(
        default_factory=list,
        description="Permission keys, e.g. ['experiments:read', 'flags:write']",
    )


class RoleUpdate(BaseModel):
    name:        str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    permissions: list[str] | None = None


class RoleResponse(RoleBase):
    id:          UUID
    permissions: list[str]
    created_at:  datetime

    model_config = {"from_attributes": True}


# ── User ↔ Roles ─────────────────────────────────────────────────────────────

class RoleSummary(BaseModel):
    id:          UUID
    key:         str
    name:        str

    model_config = {"from_attributes": True}


class UserWithRolesResponse(BaseModel):
    id:         UUID
    username:   str
    email:      str
    is_active:  bool
    is_admin:   bool
    created_at: datetime
    roles:      list[RoleSummary] = Field(default_factory=list)
    permissions: list[str]        = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AssignRoleRequest(BaseModel):
    role_id: UUID


class UserRoleAssignmentResponse(BaseModel):
    user_id:     UUID
    role_id:     UUID
    role_key:    str
    assigned_at: datetime

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    is_active: bool | None = None


# ── Pagination wrapper for role listing ──────────────────────────────────────

class PaginatedRoles(BaseModel):
    items: list[RoleResponse]
    total: int


class PaginatedUsers(BaseModel):
    items: list[UserWithRolesResponse]
    total: int
    limit: int
    offset: int
    has_next: bool
    has_prev: bool