"""
Менеджер партиций для таблицы events.

Партиция создаётся один раз на месяц: events_YYYY_MM
Вызывается из ARQ воркера ежедневно.
"""
import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _partition_name(year: int, month: int) -> str:
    return f"events_{year}_{month:02d}"


def _partition_bounds(year: int, month: int) -> tuple[str, str]:
    """Возвращает (start_date, end_date) для месячной партиции."""
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _months_ahead(base: datetime, count: int) -> list[tuple[int, int]]:
    """Генерирует (year, month) для следующих count месяцев включая текущий."""
    months = []
    year, month = base.year, base.month
    for _ in range(count):
        months.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


async def _partition_exists(db: AsyncSession, name: str) -> bool:
    """Проверяет существование таблицы-партиции в БД."""
    result = await db.execute(
        text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public'
                AND   table_name   = :name
            )
        """),
        {"name": name},
    )
    return bool(result.scalar())


async def ensure_partitions(
    db: AsyncSession,
    months_ahead: int = 3,
) -> list[str]:
    """
    Создаёт партиции для текущего и следующих months_ahead месяцев.
    Уже существующие партиции пропускает.

    Returns:
        Список имён созданных партиций (пустой если все уже существовали).

    Пример: вызов 2026-03-15, months_ahead=3
    → проверяет events_2026_03, _04, _05, _06
    → создаёт отсутствующие
    """
    now = datetime.utcnow()
    created: list[str] = []

    for year, month in _months_ahead(now, months_ahead + 1):
        name = _partition_name(year, month)

        if await _partition_exists(db, name):
            logger.debug(f"Партиция уже существует: {name}")
            continue

        start, end = _partition_bounds(year, month)
        await db.execute(
            text(
                f"CREATE TABLE {name} PARTITION OF events "
                f"FOR VALUES FROM ('{start}') TO ('{end}')"
            )
        )
        created.append(name)
        logger.info(f"Создана партиция: {name} [{start}, {end})")

    return created


async def get_partition_stats(db: AsyncSession) -> list[dict]:
    """
    Возвращает статистику по партициям events:
    имя, количество строк, размер на диске.

    Используется для мониторинга.
    """
    result = await db.execute(text("""
        SELECT
            child.relname                               AS partition_name,
            pg_size_pretty(pg_relation_size(child.oid)) AS size,
            pg_stat_get_live_tuples(child.oid)          AS row_count
        FROM pg_inherits
        JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
        JOIN pg_class child  ON pg_inherits.inhrelid  = child.oid
        WHERE parent.relname = 'events'
        ORDER BY child.relname
    """))
    return [
        {
            "partition": row.partition_name,
            "size": row.size,
            "rows": row.row_count,
        }
        for row in result
    ]
