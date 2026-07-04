import os
import sys
import time
import uuid
import random
import signal
import logging
import traceback
import threading
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select, update, text
from sqlalchemy.orm import Session

from app.core.database import engine, SessionLocal
from app.models.tenant import Queue, Project
from app.models.worker import Worker, WorkerHeartbeat
from app.models.job import Job, JobExecution, JobLog, DeadLetterJob
from app.worker.registry import registry

# Load tasks module to ensure all decorators run and register tasks
import app.worker.tasks

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("worker_engine")

class WorkerEngine:
    def __init__(self, name: str = None, max_workers: int = 5, organization_id: uuid.UUID = None, session_maker = None, db_engine = None):
        self.worker_id = uuid.uuid4()
        self.name = name or f"worker-{self.worker_id.hex[:6]}"
        self.max_workers = max_workers
        self.organization_id = organization_id
        self.session_maker = session_maker or SessionLocal
        self.engine = db_engine or engine
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.shutdown_event = threading.Event()
        self.job_notification_event = threading.Event()
        self.active_jobs = {}  # job_id -> future
        self.active_jobs_lock = threading.Lock()
        
        # Thread handles
        self.heartbeat_thread = None
        self.listener_thread = None

    def start(self):
        logger.info(f"Starting worker {self.name} (ID: {self.worker_id}) with {self.max_workers} threads...")
        
        # Register worker in database
        self._register_worker()

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        # Start heartbeat thread
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

        # Start database listen/notify thread (if supported)
        self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listener_thread.start()

        # Run main claim & execution loop
        self._main_loop()

    def _handle_signal(self, signum, frame):
        logger.info(f"Signal {signum} received. Initiating graceful shutdown...")
        self.shutdown_event.set()
        self.job_notification_event.set()  # Wake up main loop

    def _register_worker(self):
        db = self.session_maker()
        try:
            worker = Worker(
                id=self.worker_id,
                name=self.name,
                status="idle",
                system_info={
                    "max_workers": self.max_workers,
                    "pid": os.getpid(),
                    "platform": sys.platform,
                    "organization_id": str(self.organization_id) if self.organization_id else None
                }
            )
            db.add(worker)
            db.commit()
            logger.info("Worker registered in database successfully.")
        except Exception as e:
            logger.error(f"Failed to register worker in database: {e}")
            db.rollback()
            raise e
        finally:
            db.close()

    def _heartbeat_loop(self):
        while not self.shutdown_event.is_set():
            db = self.session_maker()
            try:
                # Update worker status and last_heartbeat
                db.execute(
                    update(Worker)
                    .where(Worker.id == self.worker_id)
                    .values(
                        last_heartbeat=datetime.now(timezone.utc),
                        status="active" if self.get_active_jobs_count() > 0 else "idle"
                    )
                )
                
                # Write heartbeat log
                heartbeat = WorkerHeartbeat(
                    worker_id=self.worker_id,
                    system_info={
                        "active_threads": self.get_active_jobs_count(),
                        "memory_usage": "N/A"
                    }
                )
                db.add(heartbeat)
                db.commit()
            except Exception as e:
                logger.error(f"Error in heartbeat write: {e}")
                db.rollback()
            finally:
                db.close()
            
            # Sleep 5 seconds (check shutdown event frequently)
            for _ in range(50):
                if self.shutdown_event.is_set():
                    break
                time.sleep(0.1)

    def _listen_loop(self):
        """LISTEN for job_enqueued events from PostgreSQL notify."""
        try:
            # Check if driver supports LISTEN (e.g. psycopg2) and it's not SQLite
            if "sqlite" in str(self.engine.url):
                return
            
            raw_conn = self.engine.raw_connection()
            # Set to autocommit so LISTEN works without transaction block
            raw_conn.set_isolation_level(0)
            cursor = raw_conn.cursor()
            cursor.execute("LISTEN job_enqueued;")
            logger.info("Listening for PG NOTIFY channel 'job_enqueued'...")
            
            import select as pyselect
            while not self.shutdown_event.is_set():
                if pyselect.select([raw_conn], [], [], 5.0) == ([], [], []):
                    # Timeout, check shutdown
                    continue
                else:
                    raw_conn.poll()
                    while raw_conn.notifies:
                        notify = raw_conn.notifies.pop(0)
                        logger.debug(f"Received DB notification: {notify.payload}")
                        self.job_notification_event.set()
        except Exception as e:
            logger.warning(f"LISTEN/NOTIFY not supported or failed: {e}. Falling back to standard polling.")

    def get_active_jobs_count(self) -> int:
        with self.active_jobs_lock:
            return len(self.active_jobs)

    def _main_loop(self):
        while not self.shutdown_event.is_set():
            # If the worker has thread capacity, try to claim a job
            if self.get_active_jobs_count() < self.max_workers:
                job = self._claim_job()
                if job:
                    self._dispatch_job(job)
                    continue  # Poll again immediately for more work
            
            # No job found or threads at capacity. Wait for notification or timeout.
            self.job_notification_event.wait(timeout=2.0)
            self.job_notification_event.clear()

        # Core shutdown actions
        self._perform_graceful_shutdown()

    def _claim_job(self) -> dict | None:
        db = self.session_maker()
        try:
            if "sqlite" in str(self.engine.url):
                now_param = datetime.now(timezone.utc).replace(tzinfo=None)
            else:
                now_param = datetime.now(timezone.utc)

            
            # Query for next available job in our organization context
            # We filter queues belonging to the worker's organization_id if specified.
            claim_query = """
                UPDATE jobs
                SET status = 'claimed',
                    updated_at = :now
                WHERE id = (
                    SELECT j.id
                    FROM jobs j
                    JOIN queues q ON j.queue_id = q.id
                    JOIN projects p ON q.project_id = p.id
                    WHERE j.status = 'queued'
                      AND j.scheduled_at <= :now
                      AND q.is_paused = FALSE
                      {org_filter}
                      AND (
                          SELECT COUNT(*) 
                          FROM jobs active_j 
                          WHERE active_j.queue_id = q.id 
                            AND active_j.status IN ('claimed', 'running')
                      ) < q.concurrency_limit
                    ORDER BY q.priority DESC, j.scheduled_at ASC, j.created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id, queue_id, task_name, payload, retry_count, max_retries, retry_strategy, retry_delay, backoff_factor;
            """
            
            # For SQLite compatibility in tests, remove 'FOR UPDATE SKIP LOCKED'
            if "sqlite" in str(self.engine.url):
                claim_query = """
                    UPDATE jobs
                    SET status = 'claimed',
                        updated_at = :now
                    WHERE id = (
                        SELECT j.id
                        FROM jobs j
                        JOIN queues q ON j.queue_id = q.id
                        JOIN projects p ON q.project_id = p.id
                        WHERE j.status = 'queued'
                          AND j.scheduled_at <= :now
                          AND q.is_paused = 0
                          {org_filter}
                          AND (
                              SELECT COUNT(*) 
                              FROM jobs active_j 
                              WHERE active_j.queue_id = q.id 
                                AND active_j.status IN ('claimed', 'running')
                          ) < q.concurrency_limit
                        ORDER BY q.priority DESC, j.scheduled_at ASC, j.created_at ASC
                        LIMIT 1
                    )
                    RETURNING id, queue_id, task_name, payload, retry_count, max_retries, retry_strategy, retry_delay, backoff_factor;
                """


            org_filter = ""
            params = {"now": now_param}
            if self.organization_id:
                org_filter = "AND p.organization_id = :org_id"
                if isinstance(self.organization_id, uuid.UUID):
                    params["org_id"] = self.organization_id.hex
                elif isinstance(self.organization_id, str):
                    try:
                        params["org_id"] = uuid.UUID(self.organization_id).hex
                    except ValueError:
                        params["org_id"] = self.organization_id
                else:
                    params["org_id"] = str(self.organization_id)



            formatted_query = claim_query.format(org_filter=org_filter)
            result = db.execute(text(formatted_query), params).fetchone()
            
            if result:
                db.commit()
                
                def to_uuid(val):
                    if not val:
                        return None
                    if isinstance(val, uuid.UUID):
                        return val
                    try:
                        return uuid.UUID(str(val))
                    except ValueError:
                        return val

                # Convert row to dictionary
                return {
                    "id": to_uuid(result[0]),
                    "queue_id": to_uuid(result[1]),
                    "task_name": result[2],
                    "payload": result[3],

                    "retry_count": result[4],
                    "max_retries": result[5],
                    "retry_strategy": result[6],
                    "retry_delay": result[7],
                    "backoff_factor": result[8]
                }
            return None
        except Exception as e:
            logger.error(f"Error claiming job: {e}")
            db.rollback()
            return None
        finally:
            db.close()

    def _dispatch_job(self, job: dict):
        job_id = job["id"]
        logger.info(f"Claimed job {job_id} [{job['task_name']}]. Dispatching...")
        
        # Submit task to ThreadPoolExecutor
        future = self.executor.submit(self._execute_job, job)
        
        with self.active_jobs_lock:
            self.active_jobs[job_id] = future

    def _execute_job(self, job: dict):
        job_id = job["id"]
        task_name = job["task_name"]
        payload = job["payload"] or {}
        
        # 1. Initialize execution record
        db = self.session_maker()
        execution_id = uuid.uuid4()
        try:
            # Update job status to 'running'
            db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status="running", updated_at=datetime.now(timezone.utc))
            )
            
            # Create job execution record
            execution = JobExecution(
                id=execution_id,
                job_id=job_id,
                worker_id=self.worker_id,
                status="running",
                started_at=datetime.now(timezone.utc)
            )
            db.add(execution)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to initialize job execution record for job {job_id}: {e}")
            db.rollback()
            db.close()
            self._remove_active_job(job_id)
            return

        # 2. Run the task
        start_time = time.time()
        task_log_buffer = []
        
        def log_message(level: str, msg: str):
            # Print to local logs and buffer for DB write later
            logger.info(f"[{task_name}:{str(job_id)[:6]}] {level}: {msg}")
            task_log_buffer.append({"level": level, "message": msg})

        log_message("INFO", f"Starting task {task_name}...")
        
        # Safely parse JSON string payload if needed
        import json
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception as pe:
                log_message("WARNING", f"Failed to parse payload string as JSON: {pe}")

        success = False
        result = None
        error_msg = None
        
        try:
            # Retrieve the task from registry
            func = registry.get(task_name)
            
            # Invoke function (unpack payload if dict, else pass as positional argument)
            if isinstance(payload, dict):
                result = func(**payload)
            elif isinstance(payload, list):
                result = func(*payload)
            else:
                result = func(payload)
                
            success = True
            log_message("INFO", f"Task completed successfully in {time.time() - start_time:.3f}s.")
        except Exception as e:
            success = False
            error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            log_message("ERROR", f"Task failed: {type(e).__name__}: {str(e)}")
        
        # 3. Finalize execution state and logs
        try:
            # Re-open session to commit execution results
            completed_at = datetime.now(timezone.utc)
            
            if success:
                db.execute(
                    update(JobExecution)
                    .where(JobExecution.id == execution_id)
                    .values(status="completed", completed_at=completed_at, result=result)
                )
                db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(status="completed", updated_at=completed_at)
                )
            else:
                # Execution failed. Let's record the failure details.
                db.execute(
                    update(JobExecution)
                    .where(JobExecution.id == execution_id)
                    .values(status="failed", completed_at=completed_at, error=error_msg)
                )
                
                # Process retry configuration
                self._handle_job_failure(db, job, error_msg)
                
            # Write buffered execution logs
            for log_entry in task_log_buffer:
                log = JobLog(
                    execution_id=execution_id,
                    level=log_entry["level"],
                    message=log_entry["message"]
                )
                db.add(log)
            
            db.commit()
        except Exception as e:
            logger.error(f"Failed to save job execution results to DB: {e}")
            db.rollback()
        finally:
            db.close()
            self._remove_active_job(job_id)

    def _handle_job_failure(self, db: Session, job: dict, error_msg: str):
        job_id = job["id"]
        retry_count = job["retry_count"]
        max_retries = job["max_retries"]
        retry_strategy = job["retry_strategy"]
        retry_delay = job["retry_delay"]
        backoff_factor = job["backoff_factor"]
        
        if retry_count < max_retries:
            # Determine next delay seconds
            jitter = random.uniform(0.0, 1.5)
            if retry_strategy == "linear":
                delay_sec = (retry_count + 1) * retry_delay + jitter
            elif retry_strategy == "exponential":
                delay_sec = retry_delay * (backoff_factor ** retry_count) + jitter
            else:  # fixed
                delay_sec = retry_delay + jitter
                
            next_run_at = datetime.now(timezone.utc) + timedelta(seconds=delay_sec)
            
            db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status="queued",
                    retry_count=retry_count + 1,
                    scheduled_at=next_run_at,
                    updated_at=datetime.now(timezone.utc)
                )
            )
            logger.info(f"Job {job_id} scheduled for retry {retry_count + 1}/{max_retries} in {delay_sec:.2f}s (at {next_run_at}).")
        else:
            # Max retries exceeded. Move to Dead Letter Queue (DLQ)
            db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status="dlq",
                    updated_at=datetime.now(timezone.utc)
                )
            )
            
            dlq_job = DeadLetterJob(
                job_id=job_id,
                queue_id=job["queue_id"],
                task_name=job["task_name"],
                payload=job["payload"],
                error_message=error_msg
            )
            db.add(dlq_job)
            logger.warning(f"Job {job_id} exceeded max retries ({max_retries}). Moved to Dead Letter Queue.")

    def _remove_active_job(self, job_id: uuid.UUID):
        with self.active_jobs_lock:
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]

    def _perform_graceful_shutdown(self):
        logger.info("Graceful shutdown in progress: stopping workers and clean up database...")
        
        # Mark worker status as offline
        db = self.session_maker()
        try:
            db.execute(
                update(Worker)
                .where(Worker.id == self.worker_id)
                .values(status="offline")
            )
            db.commit()
        except Exception as e:
            logger.error(f"Failed to update worker status to offline: {e}")
            db.rollback()
        finally:
            db.close()

        # Stop executing thread pool executor
        self.executor.shutdown(wait=False)
        
        # Orphaned running jobs recovery
        db = self.session_maker()
        try:
            with self.active_jobs_lock:
                active_job_ids = list(self.active_jobs.keys())
                
            if active_job_ids:
                logger.info(f"Re-queueing {len(active_job_ids)} unfinished active jobs...")
                # Reset claimed/running jobs back to queued status so other workers can pick them up
                db.execute(
                    update(Job)
                    .where(Job.id.in_(active_job_ids))
                    .values(
                        status="queued",
                        updated_at=datetime.now(timezone.utc)
                    )
                )
                
                # Set execution records to failed
                db.execute(
                    update(JobExecution)
                    .where(JobExecution.job_id.in_(active_job_ids))
                    .where(JobExecution.status == "running")
                    .values(
                        status="failed",
                        completed_at=datetime.now(timezone.utc),
                        error="Worker shut down abruptly during execution."
                    )
                )
                db.commit()
                logger.info("Active jobs successfully re-queued.")
        except Exception as e:
            logger.error(f"Failed to recover active jobs during worker shutdown: {e}")
            db.rollback()
        finally:
            db.close()

        logger.info("Worker shutdown sequence finished.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Start a job scheduler worker.")
    parser.add_argument("--name", type=str, help="Name of the worker.")
    parser.add_argument("--concurrency", type=int, default=5, help="Number of concurrent execution threads.")
    parser.add_argument("--org-id", type=str, help="Organization UUID to scope this worker.")
    args = parser.parse_args()

    org_uuid = None
    if args.org_id:
        org_uuid = uuid.UUID(args.org_id)

    worker = WorkerEngine(name=args.name, max_workers=args.concurrency, organization_id=org_uuid)
    try:
        worker.start()
    except KeyboardInterrupt:
        logger.info("Process terminated via user interrupt.")
