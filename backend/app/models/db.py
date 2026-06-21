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


class MetricAggregation(str, Enum):
    """
    How a metric collapses many events per user into one scalar.

    - count:        number of matching events (NULL `value` per event)
    - sum:          sum of `events.value` across matching events
    - avg:          mean of `events.value` across matching events
    - unique_count: count of distinct values (e.g. distinct SKU bought)
    """
    COUNT        = "count"
    SUM          = "sum"
    AVG          = "avg"
    UNIQUE_COUNT = "unique_count"


class GuardrailSeverity(str, Enum):
    WARNING  = "warning"
    CRITICAL = "critical"


class GuardrailDirection(str, Enum):
    """
    Which side of the comparison is "bad".

    - BELOW: treatment is X% LOWER than control (e.g. revenue drops)
    - ABOVE: treatment is X% HIGHER than control (e.g. error rate rises)
    """
    BELOW = "below"
    ABOVE = "above"


# `values_callable` for SAEnum columns: tells SA to serialize the
# lowercase `.value` ("sum", "below") instead of the uppercase `.name`
# ("SUM", "BELOW"). The PostgreSQL enum labels match the wire-format
# strings used by Pydantic / API clients.
_ENUM_VALUES = lambda enum: [e.value for e in enum]  # noqa: E731


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
    segments    = relationship(
        "Segment",
        secondary="experiment_segments",
        back_populates="experiments",
        lazy="selectin",
    )
    guardrails  = relationship("GuardrailConfig", back_populates="experiment", cascade="all, delete-orphan")
    holdout_group_id = Column(UUID(as_uuid=True), ForeignKey("holdout_groups.id", ondelete="SET NULL"), nullable=True)
    holdout_group    = relationship("HoldoutGroup", back_populates="experiments")
    # M-012: denormalised mirror of the latest decision's status (one of
    # "ship", "stop", "iterate", "inconclusive" — see Decision.status).
    # Updated by `services.decision_service.create_decision`. NULL means
    # "no decision has been recorded for this experiment yet".
    decision_status = Column(String(20), nullable=True)
    decisions        = relationship(
        "Decision",
        back_populates="experiment",
        cascade="all, delete-orphan",
        order_by="Decision.decided_at.asc()",
    )


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

    id                     = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id          = Column(UUID(as_uuid=True), ForeignKey("experiments.id"), nullable=False)
    name                   = Column(String(255), nullable=False)
    event_name             = Column(String(255), nullable=False)
    denominator_event_name = Column(String(255), nullable=True)
    metric_type            = Column(SAEnum(MetricType), nullable=False)
    is_primary             = Column(Boolean, default=False, nullable=False)
    is_guardrail           = Column(Boolean, default=False, nullable=False)
    # M-011: nullable so existing rows from earlier milestones stay valid.
    # When NULL, the engine infers the aggregation from `metric_type`
    # (count for conversion, sum for revenue, avg for duration).
    aggregation            = Column(SAEnum(MetricAggregation, values_callable=_ENUM_VALUES), nullable=True)
    # M-011: AND-combined property filters applied at event-read time.
    # Shape: [{"field": "country", "operator": "eq", "value": "DE"}, ...].
    # Same operators as segment_rules.
    filters                = Column(JSONB, nullable=True)
    # M-011: back-reference to the CustomMetric this row was snapshotted
    # from. NULL for hand-rolled metrics. Kept for traceability — the
    # metric continues to function if the source custom metric is deleted.
    custom_metric_id       = Column(UUID(as_uuid=True), ForeignKey("custom_metrics.id", ondelete="SET NULL"), nullable=True)
    created_at             = Column(DateTime, default=datetime.utcnow, nullable=False)

    experiment      = relationship("Experiment",    back_populates="metrics")
    results         = relationship("Result",        back_populates="metric")
    custom_metric   = relationship("CustomMetric",  back_populates="experiment_metrics")
    guardrails      = relationship("GuardrailConfig", back_populates="metric", cascade="all, delete-orphan")


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


# Feature Flags ───────────────────────────────────────────────────────
#
# M-009: Feature flag system (ADR-004). Two tables:
#
# - `feature_flags` — top-level flag config (key, kill switch, rollout).
# - `flag_rules`    — per-flag overrides. `segment_id` is reserved for
#   M-010 (Segments + Holdouts); for now it's a nullable UUID without
#   an FK. When M-010 lands, rules with a non-null `segment_id` will
#   match by segment membership; rules with NULL will act as a
#   "default for everyone" override (first by priority wins).
#
# Assignment logic (see `app/services/flag_service.py`):
#   1. flag.enabled == False → False (kill switch)
#   2. rule with no segment_id and lowest priority → use rule.rollout_percentage
#   3. otherwise → flag.rollout_percentage
#   4. Bucket user (SHA256("flag:{key}:{user_id}") % 100) — deterministic.
#   5. bucket < rollout_percentage → True, else False

class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key                = Column(String(100), nullable=False, unique=True)
    name               = Column(String(255), nullable=False)
    description        = Column(Text, nullable=True)
    enabled            = Column(Boolean, nullable=False, server_default=text("true"))
    rollout_percentage = Column(Float, nullable=False, server_default=text("0"))
    created_by         = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at         = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at         = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    rules = relationship(
        "FlagRule",
        back_populates="flag",
        cascade="all, delete-orphan",
        order_by="FlagRule.priority.asc()",
    )
    created_by_user = relationship("User")

    __table_args__ = (
        Index("ix_feature_flags_key", "key", unique=True),
    )


class FlagRule(Base):
    __tablename__ = "flag_rules"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flag_id            = Column(UUID(as_uuid=True), ForeignKey("feature_flags.id", ondelete="CASCADE"), nullable=False)
    segment_id         = Column(UUID(as_uuid=True), ForeignKey("segments.id", ondelete="SET NULL"), nullable=True)
    rollout_percentage = Column(Float, nullable=False)
    priority           = Column(Integer, nullable=False, server_default=text("0"))
    enabled            = Column(Boolean, nullable=False, server_default=text("true"))
    created_at         = Column(DateTime, default=datetime.utcnow, nullable=False)

    flag    = relationship("FeatureFlag", back_populates="rules")
    segment = relationship("Segment")

    __table_args__ = (
        Index("ix_flag_rules_flag_priority", "flag_id", "priority"),
    )


# Segments ───────────────────────────────────────────────────────────
#
# M-010 (Segments + Holdouts). A `Segment` is a named, reusable set of
# matching rules applied to a user's properties dict (sent by the SDK
# at evaluate time). `SegmentRule` rows are AND-combined.
#
# - `segments.key` is the stable identifier (e.g. "eu_users",
#   "mobile_users") — referenced from flag_rules and from
#   `experiment_segments` (M2M linking).
# - `segment_rules.value` is JSONB so `in` / `not_in` can hold arrays
#   while `eq` / `gt` / `contains` hold scalars.
# - Evaluation is server-side: `segment_service.evaluate_segment`
#   walks rules in priority order and returns whether the user
#   matches (all enabled rules must match — AND logic).

class Segment(Base):
    __tablename__ = "segments"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key         = Column(String(100), nullable=False, unique=True)
    name        = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_by  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    rules = relationship(
        "SegmentRule",
        back_populates="segment",
        cascade="all, delete-orphan",
        order_by="SegmentRule.priority.asc()",
    )
    created_by_user = relationship("User")
    experiments     = relationship(
        "Experiment",
        secondary="experiment_segments",
        back_populates="segments",
    )
    flag_rules      = relationship("FlagRule", back_populates="segment")

    __table_args__ = (
        Index("ix_segments_key", "key", unique=True),
    )


class SegmentRule(Base):
    __tablename__ = "segment_rules"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    segment_id  = Column(UUID(as_uuid=True), ForeignKey("segments.id", ondelete="CASCADE"), nullable=False)
    field       = Column(String(100), nullable=False)
    operator    = Column(String(20), nullable=False)
    value       = Column(JSONB, nullable=False)
    priority    = Column(Integer, nullable=False, server_default=text("0"))
    enabled     = Column(Boolean, nullable=False, server_default=text("true"))
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)

    segment = relationship("Segment", back_populates="rules")

    __table_args__ = (
        Index("ix_segment_rules_segment_priority", "segment_id", "priority"),
    )


class ExperimentSegment(Base):
    """
    Many-to-many: experiments ↔ segments (targeting).

    An experiment linked to a segment only assigns users who match
    that segment (see `assignment_service`). Rows are added/removed
    via the segment CRUD endpoints — no separate M2M endpoint for now.

    Pure association table — no ORM relationships declared here on
    purpose. The bidirectional M2M is wired via `secondary=` on the
    `Experiment.segments` and `Segment.experiments` relationships
    (mirrors the `user_roles` pattern from M-003).
    """
    __tablename__ = "experiment_segments"

    experiment_id = Column(UUID(as_uuid=True), ForeignKey("experiments.id", ondelete="CASCADE"), primary_key=True)
    segment_id    = Column(UUID(as_uuid=True), ForeignKey("segments.id",    ondelete="CASCADE"), primary_key=True)
    added_at      = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_experiment_segments_segment_id", "segment_id"),
    )


# Holdouts ──────────────────────────────────────────────────────────
#
# M-010 (Segments + Holdouts). A `HoldoutGroup` is a long-term
# measurement baseline: a deterministic fraction of users (e.g. 10%)
# are excluded from all linked experiments so analysts can compare
# experiment outcomes against a clean, never-exposed cohort.
#
# `holdout_exclusions` lets admins manually pull specific users
# OUT of the holdout (e.g. VIP accounts, internal staff) — even if
# they would otherwise fall in the bucketed cohort.
#
# `experiments.holdout_group_id` links an experiment to the holdout
# cohort to exclude. Assignment service checks holdout membership
# BEFORE bucket / variant pick.

class HoldoutGroup(Base):
    __tablename__ = "holdout_groups"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key         = Column(String(100), nullable=False, unique=True)
    name        = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    size_pct    = Column(Float, nullable=False, server_default=text("10"))
    is_active   = Column(Boolean, nullable=False, server_default=text("true"))
    created_by  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    exclusions      = relationship(
        "HoldoutExclusion",
        back_populates="group",
        cascade="all, delete-orphan",
    )
    experiments     = relationship("Experiment", back_populates="holdout_group")
    created_by_user = relationship("User")

    __table_args__ = (
        Index("ix_holdout_groups_key", "key", unique=True),
    )


class HoldoutExclusion(Base):
    __tablename__ = "holdout_exclusions"

    holdout_group_id = Column(UUID(as_uuid=True), ForeignKey("holdout_groups.id", ondelete="CASCADE"), primary_key=True)
    user_id          = Column(String(255), primary_key=True)
    reason           = Column(Text, nullable=True)
    excluded_by      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    excluded_at      = Column(DateTime, default=datetime.utcnow, nullable=False)

    group = relationship("HoldoutGroup", back_populates="exclusions")
    # `selectin` to avoid lazy IO — same reason as AuditLog.user above.
    user  = relationship("User", lazy="selectin")

    __table_args__ = (
        Index("ix_holdout_exclusions_user_id", "user_id"),
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

    # `selectin` avoids lazy IO when audit_service.db.refresh() runs after
    # the entry was just added — without it, the lazy `user` relationship
    # can trigger a MissingGreenlet inside the async refresh path.
    user = relationship("User", lazy="selectin")

    __table_args__ = (
        Index("ix_audit_log_created_at",    "created_at"),
        Index("ix_audit_log_user_id",       "user_id"),
        Index("ix_audit_log_resource_type", "resource_type"),
        Index("ix_audit_log_action",        "action"),
    )


# Custom Metrics ─────────────────────────────────────────────────────
#
# M-011: Reusable metric templates. A CustomMetric encodes "what to
# measure" once (event_name, aggregation, filters, denominator) and is
# snapshotted into a per-experiment `Metric` row via `custom_metric_id`
# at experiment-creation time. Editing a CustomMetric does NOT mutate
# existing experiment metrics — they are immutable snapshots. This
# keeps analysis reproducible.
#
# Filters are AND-combined and use the same operators as
# segment_rules (eq/neq/in/not_in/gt/lt/gte/lte/contains).
#
# Ratio metrics (e.g. purchases-per-session) are represented by setting
# `metric_type = REVENUE` (or DURATION) AND providing
# `denominator_event_name`. The engine's delta-method branch detects
# this automatically.
#
# `is_guardrail` on a CustomMetric is a UX hint shown in the builder;
# the engine enforces guardrail logic via per-experiment
# `GuardrailConfig` rows, not this flag.


class CustomMetric(Base):
    __tablename__ = "custom_metrics"

    id                       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key                      = Column(String(100), nullable=False, unique=True)
    name                     = Column(String(255), nullable=False)
    description              = Column(Text, nullable=True)
    event_name               = Column(String(255), nullable=False)
    aggregation              = Column(SAEnum(MetricAggregation, values_callable=_ENUM_VALUES), nullable=False)
    metric_type              = Column(SAEnum(MetricType), nullable=False)
    # AND-combined JSONB filter list applied to `events.properties`.
    filters                  = Column(JSONB, nullable=True)
    # Ratio-metric denominator — when set, metric is treated as a ratio
    # (numerator per denominator). Mutually exclusive with CONVERSION
    # (validated at the schema layer).
    denominator_event_name   = Column(String(255), nullable=True)
    denominator_aggregation  = Column(SAEnum(MetricAggregation, values_callable=_ENUM_VALUES), nullable=True)
    denominator_filters      = Column(JSONB, nullable=True)
    # Hint shown in the metric builder UI; not enforced by the engine.
    is_guardrail             = Column(Boolean, default=False, nullable=False)
    created_by               = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at               = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at               = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    experiment_metrics = relationship("Metric", back_populates="custom_metric")
    created_by_user    = relationship("User")

    __table_args__ = (
        Index("ix_custom_metrics_key", "key", unique=True),
    )


# Guardrails ────────────────────────────────────────────────────────
#
# M-011: Per-experiment guardrail threshold. A guardrail watches a
# specific Metric (where `is_guardrail=True`) and flags the experiment
# if the treatment's relative_lift crosses the configured threshold.
#
# - `direction` ("below"/"above") — which side of control is bad.
#   direction="below" + threshold_pct=5 means "if treatment is more
#   than 5% LOWER than control, fire". The most common case for
#   revenue/duration metrics.
#   direction="above" + threshold_pct=5 means "if treatment is more
#   than 5% HIGHER than control, fire". Used for error-rate type
#   guardrails where the treatment should NOT increase.
#
# - `severity` — "warning" adds an insight but does NOT block winner
#   designation. "critical" sets `metric.guardrail_violated=True` and
#   blocks any variant from being marked as `is_winner` (see
#   `app/services/stats/engine.py`).
#
# A guardrail only fires when the variant's test is statistically
# significant (avoids noise triggers). See
# `app/services/guardrail_service.evaluate_metric_guardrails`.
#
# `threshold_pct` is expressed as a positive percentage (e.g. 5.0
# means 5%). The service applies the sign internally based on
# direction.

class GuardrailConfig(Base):
    __tablename__ = "guardrail_configs"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id  = Column(UUID(as_uuid=True), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    metric_id      = Column(UUID(as_uuid=True), ForeignKey("metrics.id",     ondelete="CASCADE"), nullable=False)
    direction      = Column(SAEnum(GuardrailDirection, values_callable=_ENUM_VALUES), nullable=False)
    threshold_pct  = Column(Float, nullable=False)
    severity       = Column(SAEnum(GuardrailSeverity, values_callable=_ENUM_VALUES), nullable=False, server_default=text("'warning'"))
    # If False, the rule exists but is not evaluated. Useful when a user
    # drafts a config and wants to turn it on later without deleting it.
    is_enabled     = Column(Boolean, nullable=False, server_default=text("true"))
    created_by     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    experiment      = relationship("Experiment", back_populates="guardrails")
    metric          = relationship("Metric",     back_populates="guardrails")
    created_by_user = relationship("User")

    __table_args__ = (
        # One config per (experiment, metric, direction, severity). Two
        # guardrails on the same metric with different severities are
        # allowed (warning + critical), but you cannot duplicate them.
        UniqueConstraint(
            "experiment_id", "metric_id", "direction", "severity",
            name="uq_guardrail_exp_metric_dir_severity",
        ),
        Index("ix_guardrail_configs_experiment", "experiment_id"),
        Index("ix_guardrail_configs_metric", "metric_id"),
    )


# Decision Log ────────────────────────────────────────────────────────
#
# M-012: Append-only decision history. Each row records one decision
# ("ship" / "stop" / "iterate" / "inconclusive") taken on an
# experiment by a user, with an optional free-form comment. The log is
# immutable: there are no UPDATE or DELETE endpoints, and the model
# does not expose a `comment`-editing flow by design.
#
# `experiments.decision_status` is a denormalised mirror of the
# latest decision's `status`. The service layer keeps them in sync on
# each POST so list/detail reads don't need to JOIN.

class Decision(Base):
    __tablename__ = "decisions"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    # VARCHAR(20) (not PG ENUM) — see migration 0016 for rationale.
    # Allowed values: "ship", "stop", "iterate", "inconclusive".
    status        = Column(String(20), nullable=False)
    comment       = Column(Text, nullable=True)
    decided_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at    = Column(DateTime, default=datetime.utcnow, nullable=False)

    experiment      = relationship("Experiment", back_populates="decisions")
    # `selectin` mirrors the AuditLog pattern — avoids lazy IO when the
    # router serialises `decided_by_username` after the row was just
    # flushed inside the same request.
    decided_by_user = relationship("User", lazy="selectin")

    __table_args__ = (
        Index("ix_decisions_experiment_id", "experiment_id"),
        Index("ix_decisions_decided_at",    "decided_at"),
    )
