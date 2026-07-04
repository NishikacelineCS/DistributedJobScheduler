# Design Decisions Document

This document explains the core technical choices, architecture justifications, and implementation strategies selected for the Distributed Background Job Scheduler.

---

## 1. PostgreSQL as the Queue Broker (Instead of Redis/RabbitMQ)

### The Trade-off
Traditional background job systems like Celery use Redis or RabbitMQ as the broker. While Redis is extremely fast (in-memory), it introduces:
- Complexity in deployment and operational management (monitoring a separate database/broker instance).
- Risk of data loss (unless configured with heavy AOF/RDB persistence, which slows it down).
- Lack of transactional consistency (cannot easily coordinate database writes and job enqueuing in a single ACID transaction).

### The Solution: Postgres `FOR UPDATE SKIP LOCKED`
Since PostgreSQL 9.5, `SKIP LOCKED` allows query operations to skip rows that are currently locked by other transactions.
- **ACID Enqueue**: Enqueuing a job is as simple as inserting a row into the database. If a business logic transaction fails, the job enqueue automatically rolls back.
- **No Race Conditions**: Multiple workers can poll the same queue table without double-claiming jobs or blocking each other.
- **Simplified Stack**: A single PostgreSQL instance stores application state, tenant scopes, job metrics, and serves as the message broker.

---

## 2. Multi-Tenant Architecture: Organizations → Projects → Queues

### Security and Isolation
To support a production-grade SaaS model, security must be enforced at the database and API boundaries:
- **Tenant Scope**: A user belongs to an **Organization**. All projects, queues, jobs, and schedules are linked back to this parent.
- **API Guarding**: Every incoming request must provide a JWT containing the user's `organization_id`. We inject a dependency `get_current_tenant_context` that scopes all queries.
- **Logical Isolation**: Rather than separate schemas (which is hard to scale dynamically in real-time), we use shared-database logical isolation with strict foreign keys.
- **Queues**: A Project can have multiple Queues (e.g., `default`, `high-priority`, `heavy-compute`). This allows workers to listen selectively (e.g., Worker 1 processes `heavy-compute`, Worker 2 processes `default`).

---

## 3. Worker Communication: Listen-Notify vs. Polling

Active database polling (e.g., running `SELECT ...` every 1 second) introduces unnecessary CPU and database load when the queue is empty, yet causes latency when a job is submitted.

### Hybrid Solution
1. **PostgreSQL LISTEN / NOTIFY**:
   - When a job is enqueued (`POST /api/v1/jobs`), the API triggers a `NOTIFY job_enqueued, 'queue_id';` command.
   - Workers run a dedicated connection listening on the channel.
   - When notified, the worker immediately triggers its claiming query, skipping any sleep interval.
2. **Backoff Polling**:
   - If no notifications are received, workers poll periodically (e.g. every 5 seconds) to handle scheduled cron tasks or missed notifications.

---

## 4. Graceful Shutdown and Heartbeats

### Worker Life and Death
Workers run in untrusted nodes. They may crash, get killed by Kubernetes/Docker, or experience network partitions.
- **Heartbeat Thread**: An independent thread in each worker posts a heartbeat timestamp every 5 seconds. If a worker goes silent for >30 seconds, it is marked as `offline`.
- **Reaper Task**: The scheduler runs a background reaper task every 15 seconds. It finds any jobs marked as `running` on `offline` workers and:
  - If retry attempts are remaining, resets their status to `pending` and increments retry count.
  - If max retries are exceeded, moves them to the Dead Letter Queue (`dlq` status).

### Graceful Termination
When a worker receives `SIGTERM` or `SIGINT`:
1. It transitions its DB status to `offline` and stops pulling new jobs.
2. Active threads in the `ThreadPoolExecutor` are allowed to finish.
3. If they don't finish within the shutdown timeout (e.g. 10s), the executor is shutdown forcefully, and the worker re-enqueues the unfinished jobs in the DB.

---

## 5. Retry Strategies and Dead Letter Queue (DLQ)

Tasks can fail due to temporary external service issues (API timeouts) or permanent code bugs.

### Flexible Retries
We support three strategy types configurable per job:
- **Fixed**: Retries at constant intervals. Excellent for rate-limiting.
- **Linear**: Interval grows linearly (e.g., 5s, 10s, 15s).
- **Exponential**: Interval grows exponentially (e.g., 2s, 4s, 8s, 16s). Helps protect overloaded downstream APIs.
- **Jitter**: Adds a random variance to prevent the "Thundering Herd" problem when many failed jobs retry at the exact same millisecond.

### Dead Letter Queue (DLQ)
- Rather than discarding permanently failing jobs or looping infinitely, we isolate them under the `dlq` status.
- Jobs in the DLQ can be filtered, reviewed for stack traces, and manually re-run via a simple API call (`POST /api/v1/jobs/{job_id}/retry`), which resets their state and schedules them immediately.
