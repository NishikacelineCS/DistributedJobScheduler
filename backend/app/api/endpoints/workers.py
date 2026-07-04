import uuid
from typing import List
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.worker import Worker
from app.models.tenant import Project, Queue
from app.models.job import Job, JobExecution
from app.schemas.worker import WorkerResponse, SystemStats, QueueStatsSummary

router = APIRouter()

@router.get("", response_model=List[WorkerResponse])
def list_workers(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Workers are global, but we can filter by organization context if recorded in system_info
    # To keep simple, return all workers that belong to the user's organization or are general
    all_workers = db.query(Worker).order_by(Worker.last_heartbeat.desc()).all()
    
    # Filter workers in python if organization is stored in system_info
    scoped_workers = []
    for worker in all_workers:
        sys_info = worker.system_info or {}
        w_org = sys_info.get("organization_id")
        if not w_org or w_org == str(current_user.organization_id):
            scoped_workers.append(worker)
            
    return scoped_workers

@router.get("/stats", response_model=SystemStats)
def get_system_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Scope metrics to current user's organization
    # 1. Online workers (last heartbeat in last 30 seconds)
    heartbeat_cutoff = datetime.now(timezone.utc) - timedelta(seconds=30)
    all_workers = db.query(Worker).filter(Worker.last_heartbeat >= heartbeat_cutoff).all()
    
    online_count = 0
    for worker in all_workers:
        sys_info = worker.system_info or {}
        w_org = sys_info.get("organization_id")
        if not w_org or w_org == str(current_user.organization_id):
            online_count += 1

    # 2. Active jobs (currently running)
    running_jobs = db.query(Job).join(Queue).join(Project).filter(
        Project.organization_id == current_user.organization_id,
        Job.status == "running"
    ).count()

    # 3. Queue depth aggregates (queued, running, completed, failed, dlq)
    counts = db.query(Job.status, func.count(Job.id)).join(Queue).join(Project).filter(
        Project.organization_id == current_user.organization_id
    ).group_by(Job.status).all()
    
    stats_map = {s: 0 for s in ["queued", "running", "completed", "failed", "dlq"]}
    for status, count in counts:
        if status in stats_map:
            stats_map[status] = count

    # 4. Throughput (jobs completed in last hour)
    hour_cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    completed_last_hour = db.query(JobExecution).join(Job).join(Queue).join(Project).filter(
        Project.organization_id == current_user.organization_id,
        JobExecution.status == "completed",
        JobExecution.completed_at >= hour_cutoff
    ).count()

    return SystemStats(
        online_workers=online_count,
        active_jobs=running_jobs,
        queue_summary=QueueStatsSummary(
            total_queued=stats_map["queued"],
            total_running=stats_map["running"],
            total_completed=stats_map["completed"],
            total_failed=stats_map["failed"],
            total_dlq=stats_map["dlq"]
        ),
        throughput_last_hour=float(completed_last_hour)
    )
