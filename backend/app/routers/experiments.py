from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.db import User
from app.schemas.experiment import (
    ExperimentCreate, ExperimentListItem, ExperimentResponse,
    ExperimentStatusUpdate, MutexGroupCreate, MutexGroupResponse,
)
from app.schemas import ExperimentCreate, ExperimentUpdate, ExperimentResponse, ExperimentStatus
from app.services import experiment_service, rbac_service
from app.schemas.experiment import PaginatedExperiments

router = APIRouter()


# Experiments

@router.get("/experiments", response_model=PaginatedExperiments)
async def list_experiments(
    limit:  int = Query(default=20, ge=1, le=100, description="Элементов на странице"),
    offset: int = Query(default=0,  ge=0,          description="Смещение"),
    status: ExperimentStatus | None = Query(default=None, description="Фильтр по статусу"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("experiments:read")),
):
    items, total = await experiment_service.get_experiments(db, limit, offset, status)
    return PaginatedExperiments(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_prev=offset > 0,
    )


@router.post("/experiments", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_experiment(
    data: ExperimentCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("experiments:create")),
):
    return await experiment_service.create_experiment(db, data)


@router.get("/experiments/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("experiments:read")),
):
    experiment = await experiment_service.get_experiment_by_id(db, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Эксперимент не найден")
    return experiment


@router.patch("/experiments/{experiment_id}/status", response_model=ExperimentResponse)
async def update_status(
    experiment_id: UUID,
    data: ExperimentStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("experiments:update")),
):
    experiment = await experiment_service.get_experiment_by_id(db, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Эксперимент не найден")
    try:
        return await experiment_service.update_experiment_status(db, experiment, data.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/experiments/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_experiment(
    experiment_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("experiments:delete")),
):
    experiment = await experiment_service.get_experiment_by_id(db, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Эксперимент не найден")
    try:
        await experiment_service.delete_experiment(db, experiment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Mutex Groups

@router.get("/mutex-groups", response_model=list[MutexGroupResponse])
async def list_mutex_groups(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("experiments:read")),
):
    return await experiment_service.get_mutex_groups(db)


@router.post("/mutex-groups", response_model=MutexGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_mutex_group(
    data: MutexGroupCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("experiments:create")),
):
    return await experiment_service.create_mutex_group(db, data)