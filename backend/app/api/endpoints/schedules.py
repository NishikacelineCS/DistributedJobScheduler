import uuid
from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.tenant import Project, Queue
from app.models.schedule import Schedule
from app.schemas.schedule import ScheduleCreate, ScheduleResponse, ScheduleToggle

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

@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(sched_in: ScheduleCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Verify queue is in scope
    _verify_queue(db, sched_in.queue_id, current_user.organization_id)
    
    # Check that at least one of cron_expression or interval_seconds is set
    if not sched_in.cron_expression and not sched_in.interval_seconds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must specify either a cron_expression or interval_seconds."
        )
        
    # Check if duplicate schedule name in the organization project
    existing = db.query(Schedule).join(Queue).join(Project).filter(
        Project.organization_id == current_user.organization_id,
        Schedule.name == sched_in.name
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A schedule with name '{sched_in.name}' already exists in your organization."
        )
        
    schedule = Schedule(
        queue_id=sched_in.queue_id,
        name=sched_in.name,
        task_name=sched_in.task_name,
        cron_expression=sched_in.cron_expression,
        interval_seconds=sched_in.interval_seconds,
        payload=sched_in.payload,
        is_active=True
    )
    
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    
    # Note: APScheduler runner syncs on next polling sweep
    return schedule

@router.get("", response_model=List[ScheduleResponse])
def list_schedules(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Schedule).join(Queue).join(Project).filter(
        Project.organization_id == current_user.organization_id
    ).all()

@router.put("/{schedule_id}/toggle", response_model=ScheduleResponse)
def toggle_schedule(schedule_id: uuid.UUID, toggle_in: ScheduleToggle, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    schedule = db.query(Schedule).join(Queue).join(Project).filter(
        Schedule.id == schedule_id,
        Project.organization_id == current_user.organization_id
    ).first()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found or not in your organization."
        )
        
    schedule.is_active = toggle_in.is_active
    schedule.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(schedule)
    return schedule

@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(schedule_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    schedule = db.query(Schedule).join(Queue).join(Project).filter(
        Schedule.id == schedule_id,
        Project.organization_id == current_user.organization_id
    ).first()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found or not in your organization."
        )
        
    db.delete(schedule)
    db.commit()
    return
