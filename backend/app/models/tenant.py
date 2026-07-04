import uuid
from sqlalchemy import String, DateTime, ForeignKey, Integer, Boolean, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    users: Mapped[list["User"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    projects: Mapped[list["Project"]] = relationship(back_populates="organization", cascade="all, delete-orphan")

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="projects")
    queues: Mapped[list["Queue"]] = relationship(back_populates="project", cascade="all, delete-orphan")

class Queue(Base):
    __tablename__ = "queues"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=10, server_default="10")
    concurrency_limit: Mapped[int] = mapped_column(Integer, default=10, server_default="10")
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    
    # Queue Default Retry Policy
    default_retry_strategy: Mapped[str] = mapped_column(String(50), default="fixed", server_default="fixed")
    default_max_retries: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    default_retry_delay: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    default_backoff_factor: Mapped[float] = mapped_column(Float, default=2.0, server_default="2.0")
    
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


    # Relationships
    project: Mapped["Project"] = relationship(back_populates="queues")
    
    # Use string mapping to avoid circular import issues
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="queue", cascade="all, delete-orphan")
    schedules: Mapped[list["Schedule"]] = relationship("Schedule", back_populates="queue", cascade="all, delete-orphan")
    dead_letter_jobs: Mapped[list["DeadLetterJob"]] = relationship("DeadLetterJob", back_populates="queue", cascade="all, delete-orphan")
