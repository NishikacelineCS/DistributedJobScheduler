import uuid
from sqlalchemy import String, DateTime, ForeignKey, Integer, Boolean, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    queue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("queues.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    cron_expression: Mapped[str | None] = mapped_column(String(255), nullable=True)  # e.g., "*/5 * * * *"
    interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)     # e.g., 60
    
    payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    
    next_run_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    queue: Mapped["Queue"] = relationship("Queue", back_populates="schedules")
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="schedule")
