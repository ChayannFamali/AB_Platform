from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_sdk_scope
from app.models.db import User
from app.schemas.assignment import AssignmentRequest, AssignmentResponse
from app.services.assignment_service import get_or_create_assignment
from app.services.redis_client import get_redis

router = APIRouter()


@router.post("/assignments", response_model=AssignmentResponse)
async def assign_user(
    data: AssignmentRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    # SDK scope (NOT RBAC). Keys without `assignments:read` get 403.
    _: User = Depends(require_sdk_scope("assignments:read")),
):
    """
    Возвращает вариант эксперимента для пользователя.
    Требует X-API-Key с scope `assignments:read` или Bearer токен.
    """
    try:
        result = await get_or_create_assignment(
            db=db,
            redis=redis,
            user_id=data.user_id,
            experiment_id=data.experiment_id,
        )
    except Exception:
        return AssignmentResponse(
            assigned=False,
            variant=None,
            experiment_id=str(data.experiment_id),
        )

    if result is None:
        return AssignmentResponse(
            assigned=False,
            variant=None,
            experiment_id=str(data.experiment_id),
        )

    return AssignmentResponse(
        assigned=True,
        variant=result["variant"],
        experiment_id=result["experiment_id"],
    )