"""Partition events table by month (RANGE on occurred_at)

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-27

Что делает:
  events → events PARTITION BY RANGE (occurred_at)
  Создаёт партиции от -3 до +6 месяцев от текущей даты.
  Создаёт DEFAULT партицию как safety net.

Важно:
  PRIMARY KEY становится (id, occurred_at) — требование PostgreSQL.
  SQLAlchemy модель Event обновлена соответственно.
"""
from datetime import datetime
from alembic import op
from sqlalchemy import text

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


# Helpers ──────────────────────────────────────────────────────────────────

def _months_range(start_offset: int, end_offset: int) -> list[tuple[int, int]]:
    """Возвращает список (year, month) от now+start до now+end месяцев."""
    now = datetime.utcnow()
    months = []
    for offset in range(start_offset, end_offset + 1):
        year = now.year
        month = now.month + offset
        while month <= 0:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        months.append((year, month))
    return months


def _partition_bounds(year: int, month: int) -> tuple[str, str]:
    """Возвращает (start_date, end_date) строки для партиции месяца."""
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


# Upgrade ──────────────────────────────────────────────────────────────────

def upgrade() -> None:
    # 1. Сохраняем существующие данные
    op.execute(text("ALTER TABLE events RENAME TO events_unpartitioned"))
    op.execute(text("DROP INDEX IF EXISTS ix_events_event_time"))
    op.execute(text("DROP INDEX IF EXISTS ix_events_user_event_time"))

    # 2. Создаём новую партиционированную таблицу
    #    PRIMARY KEY ДОЛЖЕН включать ключ партиции (occurred_at)
    op.execute(text("""
        CREATE TABLE events (
            id          UUID                NOT NULL,
            user_id     VARCHAR(255)        NOT NULL,
            event_name  VARCHAR(255)        NOT NULL,
            value       DOUBLE PRECISION,
            properties  JSONB,
            occurred_at TIMESTAMP           NOT NULL,
            PRIMARY KEY (id, occurred_at)
        ) PARTITION BY RANGE (occurred_at)
    """))

    # 3. Индексы на родительской таблице → автоматически наследуются партициями
    op.execute(text(
        "CREATE INDEX ix_events_user_event_time "
        "ON events (user_id, event_name, occurred_at)"
    ))
    op.execute(text(
        "CREATE INDEX ix_events_event_time ON events (event_name, occurred_at)"
    ))

    # 4. DEFAULT партиция — safety net для данных вне диапазона конкретных партиций
    #    Важно: данные не теряются, даже если партиции на месяц ещё нет
    op.execute(text(
        "CREATE TABLE events_default PARTITION OF events DEFAULT"
    ))

    # 5. Создаём месячные партиции: -3 месяца (прошлые данные) до +6 месяцев вперёд
    for year, month in _months_range(-3, 6):
        start, end = _partition_bounds(year, month)
        name = f"events_{year}_{month:02d}"
        op.execute(text(
            f"CREATE TABLE {name} PARTITION OF events "
            f"FOR VALUES FROM ('{start}') TO ('{end}')"
        ))

    # 6. Переносим данные (PostgreSQL сам роутит по нужным партициям)
    op.execute(text("INSERT INTO events SELECT * FROM events_unpartitioned"))

    # 7. Удаляем backup таблицу
    op.execute(text("DROP TABLE events_unpartitioned"))


# Downgrade ────────────────────────────────────────────────────────────────

def downgrade() -> None:
    # 1. Восстанавливаем обычную таблицу
    op.execute(text("""
        CREATE TABLE events_restored (
            id          UUID         NOT NULL,
            user_id     VARCHAR(255) NOT NULL,
            event_name  VARCHAR(255) NOT NULL,
            value       DOUBLE PRECISION,
            properties  JSONB,
            occurred_at TIMESTAMP    NOT NULL,
            PRIMARY KEY (id)
        )
    """))

    # 2. Копируем данные обратно (читается из всех партиций через родителя)
    op.execute(text("INSERT INTO events_restored SELECT * FROM events"))

    # 3. DROP CASCADE удаляет все дочерние партиции автоматически
    op.execute(text("DROP TABLE events CASCADE"))

    # 4. Переименовываем
    op.execute(text("ALTER TABLE events_restored RENAME TO events"))

    # 5. Восстанавливаем исходные индексы
    op.execute(text(
        "CREATE INDEX ix_events_user_event_time "
        "ON events (user_id, event_name, occurred_at)"
    ))
    op.execute(text(
        "CREATE INDEX ix_events_event_time ON events (event_name, occurred_at)"
    ))
