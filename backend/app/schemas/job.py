import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator

def _make_utc(v):
    if isinstance(v, datetime):
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
    if isinstance(v, str):
        if not v.endswith('Z') and not '+' in v:
            dt = datetime.fromisoformat(v)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
    return v

class JobCreate(BaseModel):
    task_name: str = Field(..., min_length=1, max_length=255)
    payload: Optional[dict] = Field(default=None)
    queue_id: uuid.UUID
    retry_strategy: Optional[str] = Field(default="fixed")  # fixed, linear, exponential
    retry_delay: Optional[int] = Field(default=5)          # in seconds
    max_retries: Optional[int] = Field(default=3)
    backoff_factor: Optional[float] = Field(default=2.0)
    delay_seconds: Optional[int] = Field(default=0)         # for delayed jobs

class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    queue_id: uuid.UUID
    schedule_id: Optional[uuid.UUID] = None
    batch_id: Optional[Any] = None
    task_name: str
    payload: Optional[Any] = None
    status: str
    retry_count: int
    max_retries: int
    retry_strategy: str
    retry_delay: int
    backoff_factor: float
    scheduled_at: datetime
    created_at: datetime
    updated_at: datetime

    @field_validator('scheduled_at', 'created_at', 'updated_at', mode='before')
    @classmethod
    def make_utc(cls, v):
        return _make_utc(v)

class JobExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    job_id: uuid.UUID
    worker_id: Optional[uuid.UUID] = None
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None

    @field_validator('started_at', 'completed_at', mode='before')
    @classmethod
    def make_utc(cls, v):
        return _make_utc(v)

class JobLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    execution_id: uuid.UUID
    level: str
    message: str
    created_at: datetime

    @field_validator('created_at', mode='before')
    @classmethod
    def make_utc(cls, v):
        return _make_utc(v)

class JobDetailResponse(BaseModel):
    job: JobResponse
    executions: List[JobExecutionResponse] = []

class DeadLetterJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    job_id: uuid.UUID
    queue_id: uuid.UUID
    task_name: str
    payload: Optional[Any] = None
    failed_at: datetime
    error_message: Optional[str] = None

    @field_validator('failed_at', mode='before')
    @classmethod
    def make_utc(cls, v):
        return _make_utc(v)

class BatchJobCreate(BaseModel):
    jobs: List[JobCreate]

class BatchJobResponse(BaseModel):
    batch_id: uuid.UUID
    jobs: List[JobResponse]


class AISummaryResponse(BaseModel):
    job_id: uuid.UUID
    error_message: str
    ai_summary: str

