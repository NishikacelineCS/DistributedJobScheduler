import uuid
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    created_at: datetime

class QueueCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    priority: int = Field(default=10, ge=1, le=100)
    concurrency_limit: int = Field(default=10, ge=1, le=1000)

class QueueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    priority: int
    concurrency_limit: int
    is_paused: bool
    created_at: datetime

class QueuePauseRequest(BaseModel):
    is_paused: bool

class QueueStats(BaseModel):
    queue_id: uuid.UUID
    queue_name: str
    queued: int = 0
    claimed: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    dlq: int = 0
    cancelled: int = 0
