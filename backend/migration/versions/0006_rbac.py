"""RBAC tables (M-003, ADR-006)

Creates roles, role_permissions, user_roles; seeds the four predefined roles with
their permission matrix; migrates existing users (is_admin=true → admin role,
is_admin=false → viewer role). The legacy `users.is_admin` column is NOT dropped
in this migration — it stays as a deprecated read-only field for one release cycle
and will be removed in migration 0015.

Revision ID: 0006_rbac
Revises: 0005
Create Date: 2026-06-20
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

revision = "0006_rbac"
down_revision = "0005"
branch_labels = None
depends_on = None


# Permission matrix — keep in sync with docs/adr/ADR-006-rbac-model.md
_ADMIN_PERMS = (
    "experiments:read", "experiments:create", "experiments:update", "experiments:delete",
    "experiments:analyze",
    "flags:read", "flags:write",
    "segments:read", "segments:write",
    "metrics:read", "metrics:write",
    "guardrails:read", "guardrails:write",
    "holdouts:read", "holdouts:write",
    "results:read", "decisions:write",
    "webhooks:manage",
    "users:manage", "roles:manage",
    "audit:read", "settings:manage",
)

_EDITOR_PERMS = (
    "experiments:read", "experiments:create", "experiments:update", "experiments:analyze",
    "flags:read", "flags:write",
    "segments:read", "segments:write",
    "metrics:read", "metrics:write",
    "guardrails:read", "guardrails:write",
    "holdouts:read", "holdouts:write",
    "results:read", "decisions:write",
    "webhooks:manage", "audit:read",
)

_ANALYST_PERMS = (
    "experiments:read", "experiments:analyze",
    "flags:read",
    "segments:read",
    "metrics:read",
    "guardrails:read",
    "holdouts:read",
    "results:read", "audit:read",
)

_VIEWER_PERMS = (
    "experiments:read",
    "flags:read",
    "segments:read",
    "metrics:read",
    "guardrails:read",
    "holdouts:read",
    "results:read",
)


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id",          postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key",         sa.String(50),  nullable=False),
        sa.Column("name",        sa.String(100), nullable=False),
        sa.Column("description", sa.Text(),       nullable=True),
        sa.Column("created_at",  sa.DateTime(),   nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_roles_key"),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id",    postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission", sa.String(100),  nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission"),
    )
    op.create_index(
        "idx_role_permissions_permission",
        "role_permissions",
        ["permission"],
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id",     postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id",     postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_at", sa.DateTime(),  nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )
    op.create_index("idx_user_roles_role_id", "user_roles", ["role_id"])

    # ── Seed four predefined roles ─────────────────────────────────────
    op.execute("""
        INSERT INTO roles (id, key, name, description, created_at) VALUES
            (gen_random_uuid(), 'admin',   'Administrator', 'Full access',                                            now()),
            (gen_random_uuid(), 'editor',  'Editor',        'Create and modify experiments, flags, segments, metrics', now()),
            (gen_random_uuid(), 'analyst', 'Analyst',       'Read-only plus analysis',                                 now()),
            (gen_random_uuid(), 'viewer',  'Viewer',        'Read-only',                                              now());
    """)

    # ── Seed permission matrix ─────────────────────────────────────────
    # Use bound parameters (text() + bindparams) — op.execute() does not
    # accept a `params=` kwarg like SA core does.
    for perm in _ADMIN_PERMS:
        op.execute(
            text(
                "INSERT INTO role_permissions (role_id, permission) "
                "SELECT id, :p FROM roles WHERE key = 'admin'"
            ).bindparams(p=perm)
        )
    for perm in _EDITOR_PERMS:
        op.execute(
            text(
                "INSERT INTO role_permissions (role_id, permission) "
                "SELECT id, :p FROM roles WHERE key = 'editor'"
            ).bindparams(p=perm)
        )
    for perm in _ANALYST_PERMS:
        op.execute(
            text(
                "INSERT INTO role_permissions (role_id, permission) "
                "SELECT id, :p FROM roles WHERE key = 'analyst'"
            ).bindparams(p=perm)
        )
    for perm in _VIEWER_PERMS:
        op.execute(
            text(
                "INSERT INTO role_permissions (role_id, permission) "
                "SELECT id, :p FROM roles WHERE key = 'viewer'"
            ).bindparams(p=perm)
        )

    # ── Migrate existing users to RBAC ────────────────────────────────
    # is_admin=true → admin role; is_admin=false → viewer role (safe default).
    op.execute("""
        INSERT INTO user_roles (user_id, role_id, assigned_at)
        SELECT u.id, r.id, now()
        FROM users u, roles r
        WHERE u.is_admin = true AND r.key = 'admin';
    """)
    op.execute("""
        INSERT INTO user_roles (user_id, role_id, assigned_at)
        SELECT u.id, r.id, now()
        FROM users u, roles r
        WHERE u.is_admin = false AND r.key = 'viewer';
    """)


def downgrade() -> None:
    op.drop_index("idx_user_roles_role_id", table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index("idx_role_permissions_permission", table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_table("roles")