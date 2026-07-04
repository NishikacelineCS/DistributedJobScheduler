import uuid
from datetime import datetime, timezone
from typing import Optional, Any, List
from pydantic import BaseModel, ConfigDict, field_validator

class WorkerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    status: str
    last_heartbeat: datetime
    started_at: datetime
    system_info: Optional[Any] = None

    @field_validator('last_heartbeat', 'started_at', mode='before')
    @classmethod
    def make_utc(cls, v):
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

class QueueStatsSummary(BaseModel):
    total_queued: int
    total_running: int
    total_completed: int
    total_failed: int
    total_dlq: int

class SystemStats(BaseModel):
    online_workers: int
    active_jobs: int
    queue_summary: QueueStatsSummary
    throughput_last_hour: float
