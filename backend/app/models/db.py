import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float,
    ForeignKey, Index, Integer, PrimaryKeyConstraint,
    String, Text, UniqueConstraint, Enum as SAEnum, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


# Enums ─

class ExperimentStatus(str, Enum):
    DRAFT     = "draft"
    RUNNING   = "running"
    PAUSED    = "paused"
    COMPLETED = "completed"


class MetricType(str, Enum):
    CONVERSION = "conversion"
    REVENUE    = "revenue"
    DURATION   = "duration"


# MutexGroup ───────────────────────────────────────────────────────────────

class MutexGroup(Base):
    __tablename__ = "mutex_groups"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name        = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)

    experiments = relationship("Experiment", back_populates="mutex_group")


# Experiment ───────────────────────────────────────────────────────────────

class Experiment(Base):
    __tablename__ = "experiments"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                = Column(String(255), nullable=False)
    description         = Column(Text, nullable=True)
    status              = Column(SAEnum(ExperimentStatus), default=ExperimentStatus.DRAFT, nullable=False)
    traffic_percentage  = Column(Float, default=100.0, nullable=False)
    mutex_group_id      = Column(UUID(as_uuid=True), ForeignKey("mutex_groups.id"), nullable=True)
    started_at          = Column(DateTime, nullable=True)
    ended_at            = Column(DateTime, nullable=True)
    is_sequential       = Column(Boolean, default=False, nullable=False)
    created_at          = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at          = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    mutex_group = relationship("MutexGroup", back_populates="experiments")
    variants    = relationship("Variant", back_populates="experiment", cascade="all, delete-orphan")
    metrics     = relationship("Metric",  back_populates="experiment", cascade="all, delete-orphan")
    results     = relationship("Result",  back_populates="experiment", cascade="all, delete-orphan")


# Variant ──────────────────────────────────────────────────────────────────

class Variant(Base):
    __tablename__ = "variants"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("experiments.id"), nullable=False)
    name          = Column(String(100), nullable=False)
    description   = Column(Text, nullable=True)
    traffic_split = Column(Float, nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)

    experiment  = relationship("Experiment", back_populates="variants")
    assignments = relationship("Assignment", back_populates="variant")
    results     = relationship("Result",     back_populates="variant")

    __table_args__ = (
        UniqueConstraint("experiment_id", "name", name="uq_variant_experiment_name"),
    )


# Metric 

class Metric(Base):
    __tablename__ = "metrics"

    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id        = Column(UUID(as_uuid=True), ForeignKey("experiments.id"), nullable=False)
    name                 = Column(String(255), nullable=False)
    event_name           = Column(String(255), nullable=False) 
    denominator_event_name = Column(String(255), nullable=True)  
    metric_type          = Column(SAEnum(MetricType), nullable=False)
    is_primary           = Column(Boolean, default=False, nullable=False)
    is_guardrail         = Column(Boolean, default=False, nullable=False)
    created_at           = Column(DateTime, default=datetime.utcnow, nullable=False)

    experiment = relationship("Experiment", back_populates="metrics")
    results    = relationship("Result",     back_populates="metric")


# Assignment ───────────────────────────────────────────────────────────────

class Assignment(Base):
    __tablename__ = "assignments"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id       = Column(String(255), nullable=False)
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("experiments.id"), nullable=False)
    variant_id    = Column(UUID(as_uuid=True), ForeignKey("variants.id"),    nullable=False)
    variant_name  = Column(String(100), nullable=False)
    assigned_at   = Column(DateTime, default=datetime.utcnow, nullable=False)

    variant = relationship("Variant", back_populates="assignments")

    __table_args__ = (
        Index("ix_assignments_user_experiment", "user_id", "experiment_id"),
        Index("ix_assignments_experiment_time", "experiment_id", "assigned_at"),
        UniqueConstraint("user_id", "experiment_id", name="uq_assignment_user_experiment"),
    )


# Event ─

class Event(Base):
    """
    Партиционирована по occurred_at (RANGE, monthly).
    PRIMARY KEY составной — требование PostgreSQL для партиций.
    """
    __tablename__ = "events"

    id          = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)
    user_id     = Column(String(255), nullable=False)
    event_name  = Column(String(255), nullable=False)
    value       = Column(Float, nullable=True)
    properties  = Column(JSONB, nullable=True)
    occurred_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("id", "occurred_at"),
        Index("ix_events_user_event_time", "user_id", "event_name", "occurred_at"),
        Index("ix_events_event_time", "event_name", "occurred_at"),
    )


# Result 

class Result(Base):
    """Посчитанный итог эксперимента. Обновляется воркером (upsert)."""

    __tablename__ = "results"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("experiments.id"), nullable=False)
    variant_id    = Column(UUID(as_uuid=True), ForeignKey("variants.id"),    nullable=False)
    metric_id     = Column(UUID(as_uuid=True), ForeignKey("metrics.id"),     nullable=False)

    # Статистика
    sample_size              = Column(Integer, nullable=False)
    mean                     = Column(Float,   nullable=False)
    std_dev                  = Column(Float,   nullable=True)
    p_value                  = Column(Float,   nullable=True)
    confidence_interval_low  = Column(Float,   nullable=True)
    confidence_interval_high = Column(Float,   nullable=True)
    effect_size              = Column(Float,   nullable=True)
    relative_lift            = Column(Float,   nullable=True)

    # Решения
    is_significant = Column(Boolean, nullable=True)
    is_winner      = Column(Boolean, nullable=True)

    # SRM
    srm_detected = Column(Boolean, default=False, nullable=False)
    srm_p_value  = Column(Float,   nullable=True)

    is_normal         = Column(Boolean,    nullable=True)
    normality_p_value = Column(Float,      nullable=True)
    test_used         = Column(String(50), nullable=True)
    achieved_mde      = Column(Float,      nullable=True)

    numerator_mean            = Column(Float, nullable=True)
    denominator_mean          = Column(Float, nullable=True)
    numerator_relative_lift   = Column(Float, nullable=True)
    denominator_relative_lift = Column(Float, nullable=True)

    # Sequential testing (M-007) — always-valid p-value at current sample.
    # NULL for non-sequential experiments.
    sequential_fpr              = Column(Float,   nullable=True)
    sequential_boundary_crossed = Column(Boolean, nullable=True)

    # AI
    ai_interpretation = Column(Text, nullable=True)

    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    experiment = relationship("Experiment", back_populates="results")
    variant    = relationship("Variant",    back_populates="results")
    metric     = relationship("Metric",     back_populates="results")

    __table_args__ = (
        Index("ix_results_experiment", "experiment_id", "computed_at"),
        UniqueConstraint(
            "experiment_id", "variant_id", "metric_id",
            name="uq_result_exp_variant_metric"
        ),
    )


# ResultDaily 

class ResultDaily(Base):
    """
    Ежедневный снапшот результатов для trend-анализа.

    Заполняется воркером snapshot_daily_results() каждый день в 01:00 UTC.
    Используется для построения графиков динамики p-value и effect size.
    Upsert по (experiment_id, variant_id, metric_id, snapshot_date).
    """

    __tablename__ = "results_daily"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("experiments.id"), nullable=False)
    variant_id    = Column(UUID(as_uuid=True), ForeignKey("variants.id"),    nullable=False)
    metric_id     = Column(UUID(as_uuid=True), ForeignKey("metrics.id"),     nullable=False)
    snapshot_date = Column(Date, nullable=False)

    # Ключевые метрики (подмножество Result)
    sample_size    = Column(Integer, nullable=False)
    mean           = Column(Float,   nullable=False)
    p_value        = Column(Float,   nullable=True)
    effect_size    = Column(Float,   nullable=True)
    relative_lift  = Column(Float,   nullable=True)
    ci_low         = Column(Float,   nullable=True)
    ci_high        = Column(Float,   nullable=True)
    is_significant = Column(Boolean, nullable=True)
    test_used      = Column(String(50), nullable=True)
    sequential_fpr = Column(Float,   nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Однонаправленные связи — только для чтения имён в API
    variant = relationship("Variant")
    metric  = relationship("Metric")

    __table_args__ = (
        UniqueConstraint(
            "experiment_id", "variant_id", "metric_id", "snapshot_date",
            name="uq_result_daily_exp_variant_metric_date",
        ),
        Index("ix_results_daily_exp_date", "experiment_id", "snapshot_date"),
    )


# User 

class User(Base):
    __tablename__ = "users"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username        = Column(String(100),  nullable=False, unique=True)
    email           = Column(String(255),  nullable=False, unique=True)
    hashed_password = Column(String(255),  nullable=False)
    is_active       = Column(Boolean, default=True,  nullable=False)
    is_admin        = Column(Boolean, default=False, nullable=False)
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False)

    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    roles    = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy="selectin",
    )


# ApiKey 

class ApiKey(Base):
    __tablename__ = "api_keys"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name         = Column(String(255), nullable=False)
    key          = Column(String(100), nullable=False, unique=True)
    is_active    = Column(Boolean, default=True, nullable=False)
    scopes       = Column(
        JSONB,
        nullable=False,
        server_default=text('[\"assignments:read\", \"events:write\"]'),
        default=lambda: ["assignments:read", "events:write"],
    )
    created_at   = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="api_keys")

    __table_args__ = (
        Index("ix_api_keys_key",  "key"),
        Index("ix_api_keys_user", "user_id"),
    )


# RBAC ──────────────────────────────────────────────────────────────────
#
# M-003: Role-based access control (ADR-006).
# - `roles`            — predefined role definitions (admin/editor/analyst/viewer).
# - `role_permissions` — many-to-many: role → permission string.
# - `user_roles`       — many-to-many: user → role.
# `users.is_admin` is retained as a deprecated field for one release cycle
# (see migration 0015 for its removal).

class Role(Base):
    __tablename__ = "roles"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key         = Column(String(50), nullable=False, unique=True)
    name        = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)

    users       = relationship("User", secondary="user_roles", back_populates="roles")
    permissions = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("uq_roles_key", "key", unique=True),
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id    = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission = Column(String(100), primary_key=True)

    role = relationship("Role", back_populates="permissions")

    __table_args__ = (
        Index("idx_role_permissions_permission", "permission"),
    )


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id     = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_user_roles_role_id", "role_id"),
    )


# Audit Log ───────────────────────────────────────────────────────────
#
# M-004: Append-only audit trail for administrative mutations
# (role/user changes in this phase; experiment/analyze hooks in later
# tasks). Read-only via GET /api/v1/audit (requires audit:read).
#
# Schema choices:
# - `action` is a free-form string (e.g. 'create', 'update', 'delete',
#   'assign', 'revoke', 'toggle_active') — keeps the model flexible
#   without a SQL ENUM that requires migrations to add new actions.
# - `resource_type` + `resource_id` identify the affected entity;
#   `details` (JSONB) holds context-specific extras (e.g.
#   `{"role_key": "admin", "is_active": true}`). Named `details` instead
#   of `metadata` because `metadata` is reserved by SQLAlchemy's
#   Declarative API on every Base subclass.
# - No `old_value` / `new_value` full snapshots — kept minimal per the
#   M-004 design decision. Most admin actions are discoverable from the
#   current state + details.

class AuditLog(Base):
    __tablename__ = "audit_log"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action        = Column(String(50), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id   = Column(UUID(as_uuid=True), nullable=True)
    details       = Column(JSONB, nullable=True)
    ip_address    = Column(String(64), nullable=True)
    user_agent    = Column(Text, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")

    __table_args__ = (
        Index("ix_audit_log_created_at",    "created_at"),
        Index("ix_audit_log_user_id",       "user_id"),
        Index("ix_audit_log_resource_type", "resource_type"),
        Index("ix_audit_log_action",        "action"),
    )
