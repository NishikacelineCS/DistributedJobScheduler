import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict

class ScheduleCreate(BaseModel):
    queue_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    task_name: str = Field(..., min_length=1, max_length=255)
    cron_expression: Optional[str] = Field(default=None)   # e.g., "*/5 * * * *"
    interval_seconds: Optional[int] = Field(default=None)   # e.g., 60
    payload: Optional[dict] = Field(default=None)

class ScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    queue_id: uuid.UUID
    name: str
    task_name: str
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    payload: Optional[Any] = None
    is_active: bool
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class ScheduleToggle(BaseModel):
    is_active: bool
