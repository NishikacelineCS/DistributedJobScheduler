#Distributed Background Job Scheduler

A production-inspired, highly reliable, multi-tenant distributed background job scheduler similar to Celery or Sidekiq, powered by **FastAPI**, **PostgreSQL** (leveraging Row-Level Locking via `SELECT ... FOR UPDATE SKIP LOCKED` as the queue broker), **SQLAlchemy**, **APScheduler**, and a **React + Vite + Tailwind CSS** dashboard.

---

## Key Features

1. **Multi-Tenant Scoping**: Isolated workspaces scoped logically via `Organizations -> Projects -> Queues`. Users only access resources belonging to their organization.
2. **JWT Authentication**: Secure API endpoints via OAuth2 Password Bearer flow.
3. **Atomic Job Claiming**: Leverages PostgreSQL `FOR UPDATE SKIP LOCKED` to prevent double-claiming of jobs by parallel workers, ensuring exact-once processing.
4. **Flexible Retry Strategies**: Fixed delay, linear backoff, and exponential backoff configurations with random jitter to prevent thundering herd scenarios.
5. **Dead Letter Queue (DLQ)**: Permanently failing tasks (exceeding maximum retries) are moved to the DLQ for troubleshooting and manual re-run triggering.
6. **Periodic cron & interval scheduling**: Syncs database schedules dynamically into APScheduler triggers.
7. **Worker Heartbeats & Self-Healing**: Worker heartbeat sweeps identify dead worker nodes and automatically rescue orphaned running tasks back to the queue.
8. **Real-time Monitoring Dashboard**: Modern React UI to inspect queues depth, view console logs, toggle cron triggers, monitor worker health, and retry DLQ tasks.

---

## System Architecture


<img width="1225" height="980" alt="image" src="https://github.com/user-attachments/assets/07e39fe0-2ea0-4092-b3c6-01f79ab21f5c" />


## Setup & Running Instructions

### Prerequisites
- Python 3.11+
- Node.js 18+
- (Optional) PostgreSQL database

### 1. Backend Server Setup
Navigate to the `backend` folder:
```bash
cd backend
```

Create a virtual environment and install dependencies:
```bash
python -m venv venv
# On Windows
.\venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

Set environment variables (or create a `.env` file). By default, the application runs on a local SQLite database file `jobscheduler.db` automatically:
```env
# Optional: Override default SQLite database with PostgreSQL
# DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5432/jobscheduler
SECRET_KEY=supersecretjwtkeythatisverylongandsecureformultitenancy
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

Apply Alembic migrations to initialize the schema:
```bash
alembic upgrade head
```

Run the FastAPI application:
```bash
uvicorn app.main:app --reload

```
Swagger UI will be active at `http://localhost:8000/docs`.

### 2. Start a Worker Node
To start a worker processing jobs for default queues:
```bash
python -m app.worker.engine --concurrency 5
```

To scope the worker to a specific organization:
```bash
python -m app.worker.engine --concurrency 5 --org-id <org-uuid>
```

### 3. Start the Scheduling Daemon
Start the APScheduler synchronizer daemon process:
```bash
python -m app.scheduler.cron
```

### 4. React Dashboard Setup
Navigate to the `frontend` directory:
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## Running Automated Tests

We use `pytest` for unit and integration testing. Tests execute on an in-memory SQLite database configuration.

To run the complete test suite:
```bash
# In the project root directory
.\venv\Scripts\pytest .\tests
```

### Tests Coverage
- `tests/test_auth.py`: Onboarding flow, registration duplicate validation, JWT validation.
- `tests/test_worker.py`: Concurrency CLAIM lock checks, fixed/exponential retry delays, DLQ moves, and graceful shutdown recovery.
- `tests/test_api.py`: Project & queue creation, multi-tenant permission isolation checks, manual retries, and schedule CRUDs.
