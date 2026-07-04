import uuid
from sqlalchemy import String, DateTime, ForeignKey, Integer, Float, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    queue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("queues.id", ondelete="CASCADE"), nullable=False)
    schedule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(JSON, nullable=True)  # Can store batch_id as UUID or JSON list for batch jobs context
    
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="queued", server_default="queued")  # queued, scheduled, claimed, running, completed, failed, dlq, cancelled
    
    # Retry configurations
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_retries: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    retry_strategy: Mapped[str] = mapped_column(String(50), default="fixed", server_default="fixed")  # fixed, linear, exponential
    retry_delay: Mapped[int] = mapped_column(Integer, default=5, server_default="5")  # seconds
    backoff_factor: Mapped[float] = mapped_column(Float, default=2.0, server_default="2.0")
    
    scheduled_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    queue: Mapped["Queue"] = relationship("Queue", back_populates="jobs")
    schedule: Mapped["Schedule"] = relationship("Schedule", back_populates="jobs")
    executions: Mapped[list["JobExecution"]] = relationship("JobExecution", back_populates="job", cascade="all, delete-orphan")
    dlq_entry: Mapped["DeadLetterJob"] = relationship("DeadLetterJob", back_populates="job", uselist=False, cascade="all, delete-orphan")

class JobExecution(Base):
    __tablename__ = "job_executions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    worker_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workers.id", ondelete="SET NULL"), nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # running, completed, failed
    started_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="executions")
    worker: Mapped["Worker"] = relationship("Worker", back_populates="job_executions")
    logs: Mapped[list["JobLog"]] = relationship("JobLog", back_populates="execution", cascade="all, delete-orphan")

class JobLog(Base):
    __tablename__ = "job_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_executions.id", ondelete="CASCADE"), nullable=False)
    level: Mapped[str] = mapped_column(String(50), default="INFO", server_default="INFO")  # INFO, WARNING, ERROR
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    execution: Mapped["JobExecution"] = relationship("JobExecution", back_populates="logs")

class DeadLetterJob(Base):
    __tablename__ = "dead_letter_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    queue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("queues.id", ondelete="CASCADE"), nullable=False)
    
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    failed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="dlq_entry")
    queue: Mapped["Queue"] = relationship("Queue", back_populates="dead_letter_jobs")
