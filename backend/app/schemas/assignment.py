from uuid import UUID
from pydantic import BaseModel, Field


class AssignmentRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    experiment_id: UUID
    anonymous_id: str | None = None  


class AssignmentResponse(BaseModel):
    assigned: bool
    variant: str | None = None     
    experiment_id: str
