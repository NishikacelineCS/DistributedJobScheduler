import time
import uuid
import random
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import text, update
from sqlalchemy.orm import Session
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.database import SessionLocal, engine
from app.models.schedule import Schedule
from app.models.job import Job, JobExecution, DeadLetterJob
from app.models.worker import Worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("scheduler_daemon")

scheduler = BlockingScheduler()

def enqueue_scheduled_job(schedule_id: str):
    logger.info(f"Triggering scheduled job execution for schedule_id={schedule_id}")
    db = SessionLocal()
    try:
        schedule_uuid = uuid.UUID(schedule_id)
        sched = db.query(Schedule).filter(Schedule.id == schedule_uuid, Schedule.is_active == True).first()
        if not sched:
            logger.warning(f"Schedule {schedule_id} is inactive or deleted. Skipping enqueue.")
            return
            
        # Create queued job entry
        job = Job(
            queue_id=sched.queue_id,
            schedule_id=sched.id,
            task_name=sched.task_name,
            payload=sched.payload,
            status="queued",
            scheduled_at=datetime.now(timezone.utc)
        )
        db.add(job)
        
        # Update last run timestamp
        sched.last_run_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
        
        # Trigger PG notification
        try:
            db.execute(text("NOTIFY job_enqueued, :job_id"), {"job_id": str(job.id)})
            db.commit()
        except Exception:
            pass
            
        logger.info(f"Enqueued job {job.id} for schedule '{sched.name}' successfully.")
    except Exception as e:
        logger.error(f"Failed to enqueue scheduled job: {e}")
        db.rollback()
    finally:
        db.close()

def reap_dead_workers():
    logger.debug("Reaper sweeping for dead worker nodes...")
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=30)
        
        # 1. Find workers that haven't sent heartbeats in 30 seconds
        dead_workers = db.query(Worker).filter(
            Worker.last_heartbeat < cutoff,
            Worker.status != "offline"
        ).all()
        
        if not dead_workers:
            return
            
        dead_worker_ids = [w.id for w in dead_workers]
        logger.info(f"Reaper found {len(dead_workers)} dead workers: {dead_worker_ids}. Marking them offline.")
        
        # 2. Mark dead workers as offline
        db.execute(
            update(Worker)
            .where(Worker.id.in_(dead_worker_ids))
            .values(status="offline")
        )
        
        # 3. Find jobs that are marked 'running' on these offline workers
        running_jobs = db.query(Job).filter(
            Job.status == "running"
        ).join(JobExecution).filter(
            JobExecution.status == "running",
            JobExecution.worker_id.in_(dead_worker_ids)
        ).all()
        
        for job in running_jobs:
            logger.warning(f"Recovering orphaned job {job.id} from offline worker...")
            
            # Check retries limit
            if job.retry_count < job.max_retries:
                # Calculate backoff delay
                jitter = random.uniform(0.0, 1.5)
                if job.retry_strategy == "linear":
                    delay = (job.retry_count + 1) * job.retry_delay + jitter
                elif job.retry_strategy == "exponential":
                    delay = job.retry_delay * (job.backoff_factor ** job.retry_count) + jitter
                else:  # fixed
                    delay = job.retry_delay + jitter
                    
                next_run = datetime.now(timezone.utc) + timedelta(seconds=delay)
                job.status = "queued"
                job.retry_count += 1
                job.scheduled_at = next_run
                logger.info(f"Orphaned job {job.id} re-enqueued for retry {job.retry_count}/{job.max_retries} (scheduled in {delay:.2f}s).")
            else:
                job.status = "dlq"
                dlq_entry = DeadLetterJob(
                    job_id=job.id,
                    queue_id=job.queue_id,
                    task_name=job.task_name,
                    payload=job.payload,
                    error_message="Worker went offline and max retries were exceeded."
                )
                db.add(dlq_entry)
                logger.warning(f"Orphaned job {job.id} exceeded max retries. Moved to Dead Letter Queue (DLQ).")
                
            # Fail the active execution run
            db.execute(
                update(JobExecution)
                .where(JobExecution.job_id == job.id)
                .where(JobExecution.status == "running")
                .values(
                    status="failed",
                    completed_at=datetime.now(timezone.utc),
                    error="Worker went offline during execution."
                )
            )
            
        db.commit()
    except Exception as e:
        logger.error(f"Error in dead worker reaper: {e}")
        db.rollback()
    finally:
        db.close()

def sync_db_schedules():
    logger.debug("Syncing database cron schedules to APScheduler...")
    db = SessionLocal()
    try:
        # Fetch active schedules
        active_schedules = db.query(Schedule).filter(Schedule.is_active == True).all()
        active_sched_ids = {str(s.id) for s in active_schedules}
        
        # Get active jobs currently loaded in APScheduler
        apsched_jobs = {job.id: job for job in scheduler.get_jobs()}
        
        # 1. Remove jobs in APScheduler that are no longer active in DB
        for apsched_job_id in list(apsched_jobs.keys()):
            # Ignore our system tasks (reaper and sync_db_schedules)
            if apsched_job_id in ["reaper", "sync_schedules"]:
                continue
            if apsched_job_id not in active_sched_ids:
                logger.info(f"Removing inactive/deleted schedule ID {apsched_job_id} from scheduler.")
                scheduler.remove_job(apsched_job_id)
                
        # 2. Add or update active schedules
        for sched in active_schedules:
            job_id = str(sched.id)
            
            # Determine correct trigger
            if sched.cron_expression:
                trigger = CronTrigger.from_crontab(sched.cron_expression)
            elif sched.interval_seconds:
                trigger = IntervalTrigger(seconds=sched.interval_seconds)
            else:
                logger.warning(f"Schedule '{sched.name}' (ID: {sched.id}) has neither cron nor interval. Skipping.")
                continue
                
            if job_id not in apsched_jobs:
                # Add new schedule to APScheduler
                logger.info(f"Adding new schedule '{sched.name}' (ID: {sched.id}) to scheduler.")
                scheduler.add_job(
                    enqueue_scheduled_job,
                    trigger=trigger,
                    args=[job_id],
                    id=job_id,
                    max_instances=1,
                    replace_existing=True
                )
            else:
                # Update existing trigger if schedule modified
                # We can dynamically recreate it or rely on replace_existing in add_job
                # To be simple and robust, check if config matches or just always refresh
                # Refreshing is fast, we can re-schedule if parameters changed
                # To avoid excessive DB updates, we only update next_run_at in DB
                pass
                
            # Sync next run time back to DB for dashboard monitoring
            apsched_job = scheduler.get_job(job_id)
            if apsched_job and apsched_job.next_run_time:
                # Update next run time
                sched.next_run_at = apsched_job.next_run_time.astimezone(timezone.utc)
                
        db.commit()
    except Exception as e:
        logger.error(f"Error in sync_db_schedules: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("Initializing APScheduler daemon...")
    
    # 1. Register system maintenance jobs
    scheduler.add_job(
        reap_dead_workers,
        trigger=IntervalTrigger(seconds=15),
        id="reaper",
        max_instances=1,
        replace_existing=True
    )
    
    scheduler.add_job(
        sync_db_schedules,
        trigger=IntervalTrigger(seconds=10),
        id="sync_schedules",
        max_instances=1,
        replace_existing=True
    )
    
    # Run sync immediately before start
    sync_db_schedules()
    
    logger.info("Starting APScheduler BlockingScheduler...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler daemon shut down cleanly.")
