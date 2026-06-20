"""
Tests for the results CSV export endpoint (M-005).

Run:
    cd backend && PYTHONPATH=. pytest tests/test_export.py -v
"""
import csv
import io

import pytest
from httpx import AsyncClient


# ── Expected schema (per API_SPEC.md) ────────────────────────────────────────

EXPECTED_COLUMNS = [
    "metric_name",
    "variant",
    "sample_size",
    "mean",
    "std_dev",
    "p_value",
    "ci_low",
    "ci_high",
    "relative_lift",
    "is_significant",
    "is_winner",
    "test_used",
    "achieved_mde",
    "srm_detected",
    "srm_p_value",
    "sequential_fpr",
    "sequential_boundary_crossed",
]


# ═══════════════════════════════════════════════════════════════════
# 1. Error cases
# ═══════════════════════════════════════════════════════════════════

async def test_export_results_csv_404_when_no_results(
    client: AsyncClient, auth_headers: dict, running_experiment: dict
):
    """No analysis run yet → 404 with a helpful message."""
    exp_id = running_experiment["id"]
    resp = await client.get(
        f"/api/v1/experiments/{exp_id}/results/export",
        headers=auth_headers,
    )
    assert resp.status_code == 404
    assert "no results" in resp.json()["detail"].lower() or "no_results" in resp.json()["detail"].lower() \
        or "analyze" in resp.json()["detail"].lower()


async def test_export_results_csv_400_for_invalid_format(
    client: AsyncClient, auth_headers: dict, running_experiment: dict
):
    """Only csv is supported in v1."""
    resp = await client.get(
        f"/api/v1/experiments/{running_experiment['id']}/results/export"
        "?format=parquet",
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "csv" in resp.json()["detail"].lower()


async def test_export_results_csv_requires_auth(
    client: AsyncClient, running_experiment: dict
):
    """Endpoint must require JWT auth."""
    resp = await client.get(
        f"/api/v1/experiments/{running_experiment['id']}/results/export"
    )
    assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════
# 2. Successful export
# ═══════════════════════════════════════════════════════════════════

async def test_export_results_csv_returns_well_formed_csv(
    client: AsyncClient, auth_headers: dict, running_experiment: dict, engine
):
    """
    Direct DB insert of one Result row → endpoint returns RFC 4180 CSV
    with the expected columns and one data row.
    """
    from uuid import uuid4
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    exp_id = running_experiment["id"]

    # Insert one variant and one metric so the FKs in `results` resolve.
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as db:
        variant = (await db.execute(
            select(__import__('app.models.db', fromlist=['Variant']).Variant)
            .where(__import__('app.models.db', fromlist=['Variant']).Variant.experiment_id == exp_id)
        )).scalars().first()
        metric = (await db.execute(
            select(__import__('app.models.db', fromlist=['Metric']).Metric)
            .where(__import__('app.models.db', fromlist=['Metric']).Metric.experiment_id == exp_id)
        )).scalars().first()

        result = __import__('app.models.db', fromlist=['Result']).Result(
            experiment_id=exp_id,
            variant_id=variant.id,
            metric_id=metric.id,
            sample_size=5000,
            mean=0.032,
            std_dev=0.176,
            p_value=0.012,
            confidence_interval_low=0.030,
            confidence_interval_high=0.034,
            effect_size=0.0006,
            relative_lift=0.056,
            is_significant=True,
            is_winner=False,
            srm_detected=False,
            srm_p_value=None,
            is_normal=True,
            normality_p_value=0.42,
            test_used="z_test",
            achieved_mde=0.0085,
        )
        db.add(result)
        await db.commit()

    # Hit the export endpoint
    resp = await client.get(
        f"/api/v1/experiments/{exp_id}/results/export",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    assert ".csv" in resp.headers["content-disposition"]
    assert str(exp_id) in resp.headers["content-disposition"]

    # Parse the CSV
    reader = csv.DictReader(io.StringIO(resp.text))
    assert reader.fieldnames == EXPECTED_COLUMNS
    rows = list(reader)
    assert len(rows) == 1
    row = rows[0]
    assert row["metric_name"] == metric.name
    assert row["variant"] == variant.name
    assert row["sample_size"] == "5000"
    assert row["is_significant"] == "True"
    assert row["is_winner"] == "False"
    assert row["srm_detected"] == "False"
    assert row["test_used"] == "z_test"
    # Numerics formatted with full precision
    assert row["mean"].startswith("0.032")
    assert row["p_value"].startswith("0.012")


async def test_export_results_csv_multiple_rows(
    client: AsyncClient, auth_headers: dict, running_experiment: dict, engine
):
    """Two Result rows (different variants) → two CSV data rows."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.models.db import Metric, Result, Variant

    exp_id = running_experiment["id"]
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        variants = list((await db.execute(
            select(Variant).where(Variant.experiment_id == exp_id)
        )).scalars().all())
        metric = (await db.execute(
            select(Metric).where(Metric.experiment_id == exp_id)
        )).scalars().first()

        for v in variants:
            db.add(Result(
                experiment_id=exp_id,
                variant_id=v.id,
                metric_id=metric.id,
                sample_size=1000,
                mean=0.05,
                std_dev=0.22,
                test_used="z_test",
            ))
        await db.commit()

    resp = await client.get(
        f"/api/v1/experiments/{exp_id}/results/export",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    assert len(rows) == len(variants)
