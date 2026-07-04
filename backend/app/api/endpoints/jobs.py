import uuid
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, update

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.tenant import Project, Queue
from app.models.job import Job, JobExecution, JobLog, DeadLetterJob
from app.schemas.job import (
    JobCreate, JobResponse, JobDetailResponse, 
    JobExecutionResponse, JobLogResponse, 
    DeadLetterJobResponse, BatchJobCreate, BatchJobResponse,
    AISummaryResponse
)

router = APIRouter()

# Helper: verify queue belongs to current user's organization
def _verify_queue(db: Session, queue_id: uuid.UUID, organization_id: uuid.UUID) -> Queue:
    queue = db.query(Queue).join(Project).filter(
        Queue.id == queue_id,
        Project.organization_id == organization_id
    ).first()
    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue not found or not in your organization."
        )
    return queue

@router.post("", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def enqueue_job(job_in: JobCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 1. Scope check
    queue = _verify_queue(db, job_in.queue_id, current_user.organization_id)
    
    # Calculate scheduled run time
    scheduled_at = datetime.now(timezone.utc)
    if job_in.delay_seconds and job_in.delay_seconds > 0:
        scheduled_at += timedelta(seconds=job_in.delay_seconds)
        
    job = Job(
        queue_id=job_in.queue_id,
        task_name=job_in.task_name,
        payload=job_in.payload,
        status="queued",
        retry_count=0,
        max_retries=job_in.max_retries if job_in.max_retries is not None else queue.default_max_retries,
        retry_strategy=job_in.retry_strategy or queue.default_retry_strategy,
        retry_delay=job_in.retry_delay if job_in.retry_delay is not None else queue.default_retry_delay,
        backoff_factor=job_in.backoff_factor if job_in.backoff_factor is not None else queue.default_backoff_factor,
        scheduled_at=scheduled_at
    )

    
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Notify workers on PostgreSQL channel 'job_enqueued'
    try:
        db.execute(text("NOTIFY job_enqueued, :job_id"), {"job_id": str(job.id)})
        db.commit()
    except Exception:
        # SQLite does not support NOTIFY
        pass
        
    return job

@router.post("/batch", response_model=BatchJobResponse, status_code=status.HTTP_202_ACCEPTED)
def enqueue_batch_jobs(batch_in: BatchJobCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not batch_in.jobs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch list cannot be empty."
        )
        
    batch_id = uuid.uuid4()
    enqueued_jobs = []
    
    # Start transaction
    try:
        for job_in in batch_in.jobs:
            queue = _verify_queue(db, job_in.queue_id, current_user.organization_id)
            
            scheduled_at = datetime.now(timezone.utc)
            if job_in.delay_seconds and job_in.delay_seconds > 0:
                scheduled_at += timedelta(seconds=job_in.delay_seconds)
                
            job = Job(
                queue_id=job_in.queue_id,
                batch_id=str(batch_id),
                task_name=job_in.task_name,
                payload=job_in.payload,
                status="queued",
                retry_count=0,
                max_retries=job_in.max_retries if job_in.max_retries is not None else queue.default_max_retries,
                retry_strategy=job_in.retry_strategy or queue.default_retry_strategy,
                retry_delay=job_in.retry_delay if job_in.retry_delay is not None else queue.default_retry_delay,
                backoff_factor=job_in.backoff_factor if job_in.backoff_factor is not None else queue.default_backoff_factor,
                scheduled_at=scheduled_at
            )
            db.add(job)
            enqueued_jobs.append(job)

            
        db.commit()
        
        # Trigger notifications for enqueued batch
        for job in enqueued_jobs:
            try:
                db.execute(text("NOTIFY job_enqueued, :job_id"), {"job_id": str(job.id)})
            except Exception:
                pass
        try:
            db.commit()
        except Exception:
            pass
            
        # Refresh objects
        for job in enqueued_jobs:
            db.refresh(job)
            
        return BatchJobResponse(batch_id=batch_id, jobs=enqueued_jobs)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit batch: {str(e)}"
        )

@router.get("", response_model=List[JobResponse])
def list_jobs(
    queue_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    task_name: Optional[str] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Job).join(Queue).join(Project).filter(
        Project.organization_id == current_user.organization_id
    )
    
    if queue_id:
        query = query.filter(Job.queue_id == queue_id)
    if status:
        query = query.filter(Job.status == status)
    if task_name:
        query = query.filter(Job.task_name == task_name)
        
    return query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()

@router.get("/dlq", response_model=List[DeadLetterJobResponse])
def list_dlq_jobs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(DeadLetterJob).join(Queue).join(Project).filter(
        Project.organization_id == current_user.organization_id
    ).order_by(DeadLetterJob.failed_at.desc()).offset(skip).limit(limit).all()

@router.get("/{job_id}", response_model=JobDetailResponse)
def get_job_details(job_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(Job).join(Queue).join(Project).filter(
        Job.id == job_id,
        Project.organization_id == current_user.organization_id
    ).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or not in your organization."
        )
        
    executions = db.query(JobExecution).filter(JobExecution.job_id == job_id).order_by(JobExecution.started_at.desc()).all()
    return JobDetailResponse(job=job, executions=executions)

@router.get("/{job_id}/logs", response_model=List[JobLogResponse])
def get_job_logs(job_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Verify job access
    job = db.query(Job).join(Queue).join(Project).filter(
        Job.id == job_id,
        Project.organization_id == current_user.organization_id
    ).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or not in your organization."
        )
        
    return db.query(JobLog).join(JobExecution).filter(JobExecution.job_id == job_id).order_by(JobLog.created_at.asc()).all()

@router.post("/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(Job).join(Queue).join(Project).filter(
        Job.id == job_id,
        Project.organization_id == current_user.organization_id
    ).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or not in your organization."
        )
        
    if job.status not in ["queued", "scheduled", "claimed", "running"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel a job in '{job.status}' status."
        )
        
    job.status = "cancelled"
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job

@router.post("/{job_id}/retry", response_model=JobResponse)
def retry_job(job_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(Job).join(Queue).join(Project).filter(
        Job.id == job_id,
        Project.organization_id == current_user.organization_id
    ).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or not in your organization."
        )
        
    if job.status not in ["failed", "dlq", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot manually retry a job in '{job.status}' status. Must be failed, dlq, or cancelled."
        )
        
    # Reset retry counters and status back to queued, run immediately
    job.status = "queued"
    job.retry_count = 0
    job.scheduled_at = datetime.now(timezone.utc)
    job.updated_at = datetime.now(timezone.utc)
    
    # Delete DLQ record if present
    dlq_record = db.query(DeadLetterJob).filter(DeadLetterJob.job_id == job_id).first()
    if dlq_record:
        db.delete(dlq_record)
        
    db.commit()
    db.refresh(job)
    
    # Notify workers
    try:
        db.execute(text("NOTIFY job_enqueued, :job_id"), {"job_id": str(job.id)})
        db.commit()
    except Exception:
        pass
        
    return job


@router.get("/{job_id}/ai-summary", response_model=AISummaryResponse)
def get_ai_failure_summary(job_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(Job).join(Queue).join(Project).filter(
        Job.id == job_id,
        Project.organization_id == current_user.organization_id
    ).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or not in your organization."
        )
        
    last_exec = db.query(JobExecution).filter(JobExecution.job_id == job_id).order_by(JobExecution.started_at.desc()).first()
    error_msg = last_exec.error if last_exec else None
    
    if not error_msg:
        dlq_record = db.query(DeadLetterJob).filter(DeadLetterJob.job_id == job_id).first()
        error_msg = dlq_record.error_message if dlq_record else None

    if not error_msg:
        return AISummaryResponse(
            job_id=job_id,
            error_message="None",
            ai_summary="✅ Successful Execution: No errors were encountered for this background job."
        )

    err_lower = error_msg.lower()
    if "connection refused" in err_lower or "cant_connect" in err_lower or "connection timed out" in err_lower:
        ai_summary = (
            "🔌 Network Connection Failure:\n\n"
            "The worker was unable to reach a required network endpoint. "
            "Please check if the destination server or SMTP service is running, "
            "and verify that there are no active firewall rules blocking connection attempts."
        )
    elif "always_fail" in err_lower or "random_fail" in err_lower:
        ai_summary = (
            "🎯 Simulated Validation Failure:\n\n"
            "This job executed a task that is designed to fail for validation or testing purposes. "
            "The failure matches the expected testing signature. No action is required."
        )
    elif "valueerror" in err_lower or "invalid input" in err_lower:
        ai_summary = (
            "📝 Data Validation Error:\n\n"
            "The parameters provided to this task were invalid. "
            "Please inspect the job payload inputs and verify they match the required arguments schema."
        )
    else:
        ai_summary = (
            "❌ Unhandled Exception:\n\n"
            f"The job execution failed with the following traceback message: '{error_msg}'. "
            "Please review the console logs tab for full debug stack traces."
        )
        
    return AISummaryResponse(
        job_id=job_id,
        error_message=error_msg,
        ai_summary=ai_summary
    )

