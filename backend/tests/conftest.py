"""
Integration test infrastructure.

Requires: running PostgreSQL (same host as configured in settings).
Test DB:  test_<POSTGRES_DB>  (created fresh each session).

Setup sequence:
  1. Drop & create test_<db>
  2. Run Alembic migrations (same schema as production)
  3. Each test starts with clean tables (TRUNCATE before yield)
  4. DB persists after session for debugging
"""

import asyncio
import os
import subprocess
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import get_db
from app.main import app
from app.services.redis_client import get_redis

# ── Constants ─────────────────────────────────────────────────────────────────

_TEST_DB     = f"test_{settings.postgres_db}"
_TEST_DB_URL = (
    f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/{_TEST_DB}"
)
_BACKEND_DIR = Path(__file__).parent.parent   # backend/


# ── DB setup helpers ──────────────────────────────────────────────────────────

def _create_database(db_name: str) -> None:
    """Drop and recreate test database (runs before event loop)."""
    async def _inner():
        conn = await asyncpg.connect(
            host=settings.postgres_host,
            user=settings.postgres_user,
            password=settings.postgres_password,
            database="postgres",
        )
        try:
            # Force-close connections to allow DROP
            await conn.execute(f"""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = '{db_name}' AND pid <> pg_backend_pid()
            """)
            await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
            await conn.execute(f'CREATE DATABASE "{db_name}"')
        finally:
            await conn.close()

    asyncio.run(_inner())


def _run_migrations(db_name: str) -> None:
    """Apply Alembic migrations to test database.

    Uses `python -m alembic` rather than the `alembic` console script because
    the venv's shebang may point to a path that no longer exists (the script
    was generated against a different venv location). `python -m alembic`
    resolves through the active interpreter regardless.
    """
    venv_python = str(_BACKEND_DIR / ".venv" / "bin" / "python")
    env = {
        **os.environ,
        "POSTGRES_DB":       db_name,
        "POSTGRES_HOST":     settings.postgres_host,
        "POSTGRES_USER":     settings.postgres_user,
        "POSTGRES_PASSWORD": settings.postgres_password,
    }
    result = subprocess.run(
        [venv_python, "-m", "alembic", "upgrade", "head"],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(_BACKEND_DIR),
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Alembic migrations failed (code={result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
        )


# ── Session-level fixtures ────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def setup_test_database() -> None:
    """Create and migrate test database once per session."""
    _create_database(_TEST_DB)
    _run_migrations(_TEST_DB)
    yield
    # DB stays after session — useful for manual debugging


@pytest.fixture(scope="session")
def engine(setup_test_database):
    """
    Session-scoped SQLAlchemy engine.
    NullPool ensures no connection reuse across tests.
    """
    _engine = create_async_engine(
        _TEST_DB_URL, 
        echo=False, 
        poolclass=NullPool
    )
    yield _engine
    asyncio.run(_engine.dispose())


# ── Redis setup ───────────────────────────────────────────────────────────────

from unittest.mock import AsyncMock

@pytest_asyncio.fixture
async def redis_client():
    """Mock Redis для тестов (избегаем проблем с event loop)."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.setex = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.ping = AsyncMock(return_value=True)
    mock.flushdb = AsyncMock(return_value=True)
    mock.aclose = AsyncMock(return_value=None)
    return mock


@pytest_asyncio.fixture(autouse=True)
async def clean_redis(redis_client):
    """Сбрасываем моки перед каждым тестом."""
    redis_client.reset_mock()
    redis_client.get.reset_mock()
    redis_client.setex.reset_mock()
    yield



# ── Per-test isolation ────────────────────────────────────────────────────────

# Standard roles + permissions seeded per test (mirrors migration 0006_rbac).
# Kept in sync with backend/app/services/rbac_service.py::ROLE_PERMISSIONS.
_STANDARD_ROLES = [
    ("admin",   "Administrator",       "Full access"),
    ("editor",  "Editor",              "Can create and modify experiments"),
    ("analyst", "Analyst",             "Read-only plus analysis"),
    ("viewer",  "Viewer",              "Read-only"),
]
from app.services.rbac_service import ROLE_PERMISSIONS  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def clean_tables() -> None:
    """
    Truncate all tables BEFORE each test, then re-seed the 4 standard roles
    so first-user registration in M-003 tests still assigns admin. We can't
    rely on migration seed because earlier tests in the session may have
    added custom roles that would break later assertions on
    `len(roles) == 4`.
    """
    conn = await asyncpg.connect(
        host=settings.postgres_host,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=_TEST_DB,
    )
    try:
        await conn.execute("""
            TRUNCATE
                api_keys,
                users,
                user_roles,
                role_permissions,
                roles,
                audit_log,
                results_daily,
                results,
                events,
                assignments,
                metrics,
                variants,
                experiments,
                mutex_groups,
                flag_rules,
                feature_flags
            CASCADE
        """)
        # Re-seed standard roles + their permission sets.
        for key, name, description in _STANDARD_ROLES:
            role_id = await conn.fetchval(
                "INSERT INTO roles (id, key, name, description, created_at) "
                "VALUES (gen_random_uuid(), $1, $2, $3, now()) RETURNING id",
                key, name, description,
            )
            for perm in ROLE_PERMISSIONS[key]:
                await conn.execute(
                    "INSERT INTO role_permissions (role_id, permission) "
                    "VALUES ($1, $2)",
                    role_id, perm,
                )
    finally:
        await conn.close()


# ── HTTP client ───────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(engine, redis_client) -> AsyncClient:
    """
    Async HTTP client connected to FastAPI app,
    with the test database and Redis injected via dependency override.
    """
    TestSession = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _override_get_db():
        async with TestSession() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def _override_get_redis():
        return redis_client

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis 

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Auth fixtures ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict:
    """Register user (first → admin), login, return Bearer headers."""
    await client.post("/api/v1/auth/register", json={
        "username": "testuser",
        "email":    "test@example.com",
        "password": "testpassword123",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email":    "test@example.com",
        "password": "testpassword123",
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture
async def api_key_headers(client: AsyncClient, auth_headers: dict) -> dict:
    """Create SDK API key, return X-API-Key headers."""
    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "test-sdk-key"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return {"X-API-Key": resp.json()["key"]}


# ── Experiment factories ───────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def conversion_experiment(client: AsyncClient, auth_headers: dict) -> dict:
    """Draft conversion experiment."""
    resp = await client.post("/api/v1/experiments", json={
        "name": "Button Colour Test",
        "variants": [
            {"name": "control",   "traffic_split": 50},
            {"name": "treatment", "traffic_split": 50},
        ],
        "metrics": [{
            "name":        "Click Rate",
            "event_name":  "button_click",
            "metric_type": "conversion",
            "is_primary":  True,
        }],
    }, headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def running_experiment(
    client: AsyncClient, auth_headers: dict, conversion_experiment: dict
) -> dict:
    """conversion_experiment transitioned to RUNNING state."""
    exp_id = conversion_experiment["id"]
    resp = await client.patch(
        f"/api/v1/experiments/{exp_id}/status",
        json={"status": "running"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    return resp.json()
