import uuid
import pytest
from datetime import datetime, timezone, timedelta
from app.models.tenant import Organization, Project, Queue
from app.models.job import Job, JobExecution, DeadLetterJob
from app.models.worker import Worker
from app.worker.engine import WorkerEngine
from app.worker.registry import registry
from conftest import TestingSessionLocal, engine
from sqlalchemy import text

@pytest.fixture(scope="function")
def setup_tenant_data(db):
    org = Organization(name="Test Org")
    db.add(org)
    db.flush()

    project = Project(organization_id=org.id, name="Test Project")
    db.add(project)
    db.flush()

    queue = Queue(project_id=project.id, name="default", priority=10, concurrency_limit=5)
    db.add(queue)
    db.commit()

    return {"org": org, "project": project, "queue": queue}

def test_atomic_job_claiming(db, setup_tenant_data):
    queue = setup_tenant_data["queue"]
    
    # Enqueue two jobs
    job1 = Job(
        queue_id=queue.id,
        task_name="send_email",
        payload={"email": "first@example.com", "subject": "test", "body": "test"},
        status="queued",
        scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1)
    )
    job2 = Job(
        queue_id=queue.id,
        task_name="send_email",
        payload={"email": "second@example.com", "subject": "test", "body": "test"},
        status="queued",
        scheduled_at=datetime.now(timezone.utc) - timedelta(seconds=30)
    )
    db.add_all([job1, job2])
    db.commit()

    # Print diagnostic info
    print("\n--- Diagnostic Info ---")
    print("Now param:", datetime.now(timezone.utc))
    for j in db.query(Job).all():
        print(f"Job: id={j.id}, status={j.status}, scheduled_at={j.scheduled_at}, type(scheduled_at)={type(j.scheduled_at)}")
    for q in db.query(Queue).all():
        print(f"Queue: id={q.id}, name={q.name}, is_paused={q.is_paused}, type(is_paused)={type(q.is_paused)}")
    for p in db.query(Project).all():
        print(f"Project: id={p.id}, name={p.name}, org_id={p.organization_id}, type(org_id)={type(p.organization_id)}")
    for o in db.query(Organization).all():
        print(f"Org: id={o.id}, name={o.name}")
    
    raw_org_id = db.execute(text("SELECT organization_id FROM projects")).fetchone()[0]
    print(f"Raw organization_id in DB: {raw_org_id!r}, type={type(raw_org_id)}")


    # Worker Engine instance
    worker1 = WorkerEngine(
        name="worker-1", 
        max_workers=2, 
        organization_id=setup_tenant_data["org"].id,
        session_maker=TestingSessionLocal,
        db_engine=engine
    )
    worker2 = WorkerEngine(
        name="worker-2", 
        max_workers=2, 
        organization_id=setup_tenant_data["org"].id,
        session_maker=TestingSessionLocal,
        db_engine=engine
    )
    
    # Simulate worker-1 claiming a job
    claimed1 = worker1._claim_job()
    assert claimed1 is not None
    assert claimed1["id"] in [job1.id, job2.id]
    
    # Simulate worker-2 claiming a job (should get the remaining job)
    claimed2 = worker2._claim_job()
    assert claimed2 is not None
    assert claimed2["id"] in [job1.id, job2.id]
    assert claimed1["id"] != claimed2["id"]

    # Try to claim again (no more queued jobs)
    claimed3 = worker1._claim_job()
    assert claimed3 is None

def test_retry_strategy_fixed(db, setup_tenant_data):
    queue = setup_tenant_data["queue"]
    
    job = Job(
        queue_id=queue.id,
        task_name="always_fail",
        payload={"reason": "Fixed test failure"},
        status="queued",
        retry_count=0,
        max_retries=3,
        retry_strategy="fixed",
        retry_delay=10,
        scheduled_at=datetime.now(timezone.utc)
    )
    db.add(job)
    db.commit()

    worker = WorkerEngine(
        name="test-worker", 
        max_workers=1, 
        organization_id=setup_tenant_data["org"].id,
        session_maker=TestingSessionLocal,
        db_engine=engine
    )
    
    # Run the worker execution of this job synchronously
    job_dict = {
        "id": job.id,
        "queue_id": queue.id,
        "task_name": job.task_name,
        "payload": job.payload,
        "retry_count": job.retry_count,
        "max_retries": job.max_retries,
        "retry_strategy": job.retry_strategy,
        "retry_delay": job.retry_delay,
        "backoff_factor": job.backoff_factor
    }
    
    worker._execute_job(job_dict)
    
    # Re-fetch job state
    db.expire_all()
    db_job = db.query(Job).filter(Job.id == job.id).first()
    assert db_job.status == "queued"
    assert db_job.retry_count == 1
    # Next scheduled time should be roughly now + 10s
    time_diff = db_job.scheduled_at.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
    assert 5 < time_diff.total_seconds() < 13

def test_retry_strategy_exponential(db, setup_tenant_data):
    queue = setup_tenant_data["queue"]
    
    job = Job(
        queue_id=queue.id,
        task_name="always_fail",
        payload={"reason": "Expo test failure"},
        status="queued",
        retry_count=2, # third run attempt
        max_retries=5,
        retry_strategy="exponential",
        retry_delay=5,
        backoff_factor=3.0,
        scheduled_at=datetime.now(timezone.utc)
    )
    db.add(job)
    db.commit()

    worker = WorkerEngine(
        name="test-worker", 
        max_workers=1, 
        organization_id=setup_tenant_data["org"].id,
        session_maker=TestingSessionLocal,
        db_engine=engine
    )
    
    job_dict = {
        "id": job.id,
        "queue_id": queue.id,
        "task_name": job.task_name,
        "payload": job.payload,
        "retry_count": job.retry_count,
        "max_retries": job.max_retries,
        "retry_strategy": job.retry_strategy,
        "retry_delay": job.retry_delay,
        "backoff_factor": job.backoff_factor
    }
    
    worker._execute_job(job_dict)
    
    # Re-fetch job
    db.expire_all()
    db_job = db.query(Job).filter(Job.id == job.id).first()
    assert db_job.status == "queued"
    assert db_job.retry_count == 3
    # Delay should be 5 * (3.0 ** 2) = 45s + jitter
    time_diff = db_job.scheduled_at.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
    assert 40 < time_diff.total_seconds() < 49

def test_dead_letter_queue(db, setup_tenant_data):
    queue = setup_tenant_data["queue"]
    
    job = Job(
        queue_id=queue.id,
        task_name="always_fail",
        payload={"reason": "DLQ test failure"},
        status="queued",
        retry_count=3,
        max_retries=3,  # Max retries hit
        retry_strategy="fixed",
        retry_delay=5,
        scheduled_at=datetime.now(timezone.utc)
    )
    db.add(job)
    db.commit()

    worker = WorkerEngine(
        name="test-worker", 
        max_workers=1, 
        organization_id=setup_tenant_data["org"].id,
        session_maker=TestingSessionLocal,
        db_engine=engine
    )
    
    job_dict = {
        "id": job.id,
        "queue_id": queue.id,
        "task_name": job.task_name,
        "payload": job.payload,
        "retry_count": job.retry_count,
        "max_retries": job.max_retries,
        "retry_strategy": job.retry_strategy,
        "retry_delay": job.retry_delay,
        "backoff_factor": job.backoff_factor
    }
    
    worker._execute_job(job_dict)
    
    # Re-fetch job
    db.expire_all()
    db_job = db.query(Job).filter(Job.id == job.id).first()
    assert db_job.status == "dlq"
    
    # Verify DLQ entry exists
    dlq_entry = db.query(DeadLetterJob).filter(DeadLetterJob.job_id == job.id).first()
    assert dlq_entry is not None
    assert dlq_entry.task_name == "always_fail"
    assert "ValueError" in dlq_entry.error_message

def test_graceful_shutdown_recovery(db, setup_tenant_data):
    queue = setup_tenant_data["queue"]
    
    job = Job(
        id=uuid.uuid4(),
        queue_id=queue.id,
        task_name="send_email",
        payload={},
        status="running"
    )
    db.add(job)
    
    # Mock active worker registration and run status
    worker_id = uuid.uuid4()
    worker_rec = Worker(id=worker_id, name="dying-worker", status="active")
    db.add(worker_rec)
    db.flush()
    
    execution = JobExecution(
        id=uuid.uuid4(),
        job_id=job.id,
        worker_id=worker_id,
        status="running"
    )
    db.add(execution)
    db.commit()

    # Instantiate engine with exact worker ID
    worker = WorkerEngine(
        name="dying-worker", 
        max_workers=1, 
        organization_id=setup_tenant_data["org"].id,
        session_maker=TestingSessionLocal,
        db_engine=engine
    )
    worker.worker_id = worker_id
    
    # Populate the active jobs dict as if it's currently running
    worker.active_jobs[job.id] = None
    
    # Run graceful shutdown logic directly
    worker._perform_graceful_shutdown()
    
    # Re-fetch state
    db.expire_all()
    db_job = db.query(Job).filter(Job.id == job.id).first()
    db_exec = db.query(JobExecution).filter(JobExecution.job_id == job.id).first()
    db_worker = db.query(Worker).filter(Worker.id == worker_id).first()
    
    assert db_job.status == "queued"
    assert db_exec.status == "failed"
    assert "abruptly" in db_exec.error
    assert db_worker.status == "offline"


def test_queue_concurrency_limit(db, setup_tenant_data):
    queue = setup_tenant_data["queue"]
    queue_id = queue.id
    
    # Set limit to 1
    queue.concurrency_limit = 1
    db.commit()
    
    # Create running job
    running_job = Job(
        queue_id=queue_id,
        task_name="send_email",
        status="running",
        scheduled_at=datetime.now(timezone.utc)
    )
    db.add(running_job)
    db.commit()
    running_job_id = running_job.id
    
    # Create queued job
    queued_job = Job(
        queue_id=queue_id,
        task_name="send_email",
        status="queued",
        scheduled_at=datetime.now(timezone.utc)
    )
    db.add(queued_job)
    db.commit()
    queued_job_id = queued_job.id
    
    worker = WorkerEngine(
        name="test-concurrency-worker",
        max_workers=1,
        organization_id=setup_tenant_data["org"].id,
        session_maker=lambda: db,
        db_engine=engine
    )

    
    # Worker shouldn't claim because running_job count (1) >= concurrency_limit (1)
    claimed = worker._claim_job()
    assert claimed is None
    
    # Mark running job completed using bulk update to prevent ORM expiration errors
    db.query(Job).filter(Job.id == running_job_id).update({"status": "completed"})
    db.commit()
    
    # Now it should claim
    claimed = worker._claim_job()
    assert claimed is not None
    assert claimed["id"] == queued_job_id



