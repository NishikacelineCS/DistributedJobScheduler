import uuid
from sqlalchemy import String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Worker(Base):
    __tablename__ = "workers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="idle", server_default="idle")  # active, idle, offline
    last_heartbeat: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    system_info: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)

    # Relationships
    heartbeats: Mapped[list["WorkerHeartbeat"]] = relationship(back_populates="worker", cascade="all, delete-orphan")
    job_executions: Mapped[list["JobExecution"]] = relationship("JobExecution", back_populates="worker")

class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    worker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"), nullable=False)
    timestamp: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    system_info: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)

    # Relationships
    worker: Mapped["Worker"] = relationship(back_populates="heartbeats")
