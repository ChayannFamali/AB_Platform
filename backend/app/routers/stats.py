from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.dependencies import get_current_user
from app.models.db import User
from app.services.stats.sample_size import calculate_for_conversion, calculate_for_revenue

router = APIRouter()


class SampleSizeResponse(BaseModel):
    sample_size_per_variant: int
    total_sample_size: int
    baseline_rate: float
    target_rate: float
    mde: float
    alpha: float
    power: float
    days_needed: int | None


@router.get("/stats/sample-size/conversion", response_model=SampleSizeResponse)
async def sample_size_conversion(
    baseline_rate: float = Query(..., gt=0, lt=1,
                                 description="Текущая конверсия (0.032 = 3.2%)"),
    mde:           float = Query(..., gt=0, lt=1,
                                 description="Минимальный эффект (0.005 = +0.5%)"),
    alpha:         float = Query(default=0.05, gt=0, lt=1),
    power:         float = Query(default=0.80, gt=0, lt=1),
    daily_traffic: int | None = Query(default=None, gt=0),
    _: User = Depends(get_current_user),
):
    if baseline_rate + mde >= 1:
        raise HTTPException(
            status_code=400,
            detail=f"baseline_rate + mde = {baseline_rate + mde:.3f} ≥ 1.",
        )
    try:
        result = calculate_for_conversion(baseline_rate, mde, alpha, power, daily_traffic)
    except (ValueError, OverflowError) as e:
        raise HTTPException(status_code=400, detail=f"Ошибка расчёта: {e}")
    return SampleSizeResponse(**result.__dict__)


@router.get("/stats/sample-size/revenue", response_model=SampleSizeResponse)
async def sample_size_revenue(
    baseline_mean: float = Query(..., gt=0),
    baseline_std:  float = Query(..., gt=0),
    mde_absolute:  float = Query(..., gt=0),
    alpha:         float = Query(default=0.05, gt=0, lt=1),
    power:         float = Query(default=0.80, gt=0, lt=1),
    daily_traffic: int | None = Query(default=None, gt=0),
    _: User = Depends(get_current_user),
):
    try:
        result = calculate_for_revenue(
            baseline_mean, baseline_std, mde_absolute, alpha, power, daily_traffic
        )
    except (ValueError, OverflowError) as e:
        raise HTTPException(status_code=400, detail=f"Ошибка расчёта: {e}")
    return SampleSizeResponse(**result.__dict__)
