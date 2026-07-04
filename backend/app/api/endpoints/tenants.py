import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.tenant import Project, Queue
from app.models.job import Job
from app.schemas.tenant import ProjectCreate, ProjectResponse, QueueCreate, QueueResponse, QueuePauseRequest, QueueStats

router = APIRouter()

# ----------------- Projects -----------------

@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(project_in: ProjectCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = Project(
        organization_id=current_user.organization_id,
        name=project_in.name
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

@router.get("/projects", response_model=List[ProjectResponse])
def list_projects(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Project).filter(Project.organization_id == current_user.organization_id).all()

# ----------------- Queues -----------------

@router.post("/projects/{project_id}/queues", response_model=QueueResponse, status_code=status.HTTP_201_CREATED)
def create_queue(project_id: uuid.UUID, queue_in: QueueCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Verify project belongs to current organization
    project = db.query(Project).filter(Project.id == project_id, Project.organization_id == current_user.organization_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or not in your organization."
        )
    
    queue = Queue(
        project_id=project_id,
        name=queue_in.name,
        priority=queue_in.priority,
        concurrency_limit=queue_in.concurrency_limit
    )
    db.add(queue)
    db.commit()
    db.refresh(queue)
    return queue

@router.get("/projects/{project_id}/queues", response_model=List[QueueResponse])
def list_queues(project_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Verify project belongs to current organization
    project = db.query(Project).filter(Project.id == project_id, Project.organization_id == current_user.organization_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or not in your organization."
        )
    return db.query(Queue).filter(Queue.project_id == project_id).all()

@router.put("/queues/{queue_id}/pause", response_model=QueueResponse)
def toggle_pause_queue(queue_id: uuid.UUID, pause_in: QueuePauseRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Verify queue belongs to current organization project
    queue = db.query(Queue).join(Project).filter(
        Queue.id == queue_id,
        Project.organization_id == current_user.organization_id
    ).first()
    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue not found or not in your organization."
        )
    
    queue.is_paused = pause_in.is_paused
    db.commit()
    db.refresh(queue)
    return queue

@router.get("/queues/{queue_id}/stats", response_model=QueueStats)
def get_queue_stats(queue_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Verify queue belongs to current organization project
    queue = db.query(Queue).join(Project).filter(
        Queue.id == queue_id,
        Project.organization_id == current_user.organization_id
    ).first()
    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue not found or not in your organization."
        )
    
    # Calculate counts dynamically
    statuses = ["queued", "claimed", "running", "completed", "failed", "dlq", "cancelled"]
    stats = {status: 0 for status in statuses}
    
    # Executing raw counts aggregations
    counts = db.query(Job.status, text("count(*)")).filter(Job.queue_id == queue_id).group_by(Job.status).all()
    for status, count in counts:
        if status in stats:
            stats[status] = count
            
    return QueueStats(
        queue_id=queue_id,
        queue_name=queue.name,
        queued=stats["queued"],
        claimed=stats["claimed"],
        running=stats["running"],
        completed=stats["completed"],
        failed=stats["failed"],
        dlq=stats["dlq"],
        cancelled=stats["cancelled"]
    )
