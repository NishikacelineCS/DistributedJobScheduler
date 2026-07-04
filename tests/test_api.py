import uuid
import pytest
from datetime import datetime, timezone

@pytest.fixture(scope="function")
def auth_headers_org_a(client):
    # Register Org A
    reg_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "userA@example.com",
            "password": "passwordA",
            "organization_name": "Org A"
        }
    )
    assert reg_response.status_code == 201
    
    # Login Org A
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "userA@example.com", "password": "passwordA"}
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="function")
def auth_headers_org_b(client):
    # Register Org B
    reg_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "userB@example.com",
            "password": "passwordB",
            "organization_name": "Org B"
        }
    )
    assert reg_response.status_code == 201
    
    # Login Org B
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "userB@example.com", "password": "passwordB"}
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_project_and_queue_crud(client, auth_headers_org_a):
    # Create Project
    response = client.post("/api/v1/projects", json={"name": "Alpha Project"}, headers=auth_headers_org_a)
    assert response.status_code == 201
    project_data = response.json()
    assert project_data["name"] == "Alpha Project"
    project_id = project_data["id"]

    # Create Queue under Project
    queue_resp = client.post(
        f"/api/v1/projects/{project_id}/queues",
        json={"name": "fast-queue", "priority": 80, "concurrency_limit": 20},
        headers=auth_headers_org_a
    )
    assert queue_resp.status_code == 201
    queue_data = queue_resp.json()
    assert queue_data["name"] == "fast-queue"
    assert queue_data["priority"] == 80
    assert queue_data["concurrency_limit"] == 20
    queue_id = queue_data["id"]

    # List Projects
    projects_resp = client.get("/api/v1/projects", headers=auth_headers_org_a)
    assert len(projects_resp.json()) == 1

    # List Queues
    queues_resp = client.get(f"/api/v1/projects/{project_id}/queues", headers=auth_headers_org_a)
    assert len(queues_resp.json()) == 1

    # Pause Queue
    pause_resp = client.put(f"/api/v1/queues/{queue_id}/pause", json={"is_paused": True}, headers=auth_headers_org_a)
    assert pause_resp.status_code == 200
    assert pause_resp.json()["is_paused"] is True

def test_multi_tenancy_isolation(client, auth_headers_org_a, auth_headers_org_b):
    # Create Project in Org A
    resp_a = client.post("/api/v1/projects", json={"name": "Org A Project"}, headers=auth_headers_org_a)
    project_id_a = resp_a.json()["id"]

    # Org B trying to list projects should NOT see Org A's project
    projects_b = client.get("/api/v1/projects", headers=auth_headers_org_b).json()
    assert len(projects_b) == 0

    # Org B trying to create queue under Org A project should be denied
    resp_bad = client.post(
        f"/api/v1/projects/{project_id_a}/queues",
        json={"name": "stolen-queue", "priority": 10},
        headers=auth_headers_org_b
    )
    assert resp_bad.status_code == 404
    assert "not found" in resp_bad.json()["detail"].lower()

def test_jobs_management(client, auth_headers_org_a):
    # Create project and queue
    proj = client.post("/api/v1/projects", json={"name": "Job Proj"}, headers=auth_headers_org_a).json()
    queue = client.post(
        f"/api/v1/projects/{proj['id']}/queues",
        json={"name": "default", "priority": 10},
        headers=auth_headers_org_a
    ).json()

    # Enqueue a job
    job_resp = client.post(
        "/api/v1/jobs",
        json={
            "task_name": "send_email",
            "payload": {"email": "hello@world.com", "subject": "hi", "body": "test"},
            "queue_id": queue["id"]
        },
        headers=auth_headers_org_a
    )
    assert job_resp.status_code == 202
    job_data = job_resp.json()
    assert job_data["task_name"] == "send_email"
    assert job_data["status"] == "queued"
    job_id = job_data["id"]

    # Get Job Details
    details = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers_org_a).json()
    assert details["job"]["id"] == job_id
    assert len(details["executions"]) == 0

    # Cancel Job
    cancel_resp = client.post(f"/api/v1/jobs/{job_id}/cancel", headers=auth_headers_org_a)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    # Retry Job
    retry_resp = client.post(f"/api/v1/jobs/{job_id}/retry", headers=auth_headers_org_a)
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == "queued"

def test_schedules_crud(client, auth_headers_org_a):
    # Create project and queue
    proj = client.post("/api/v1/projects", json={"name": "Sched Proj"}, headers=auth_headers_org_a).json()
    queue = client.post(
        f"/api/v1/projects/{proj['id']}/queues",
        json={"name": "default", "priority": 10},
        headers=auth_headers_org_a
    ).json()

    # Create Schedule
    sched_resp = client.post(
        "/api/v1/schedules",
        json={
            "queue_id": queue["id"],
            "name": "Hourly Sync",
            "task_name": "send_email",
            "cron_expression": "0 * * * *",
            "payload": {"email": "admin@org.com", "subject": "Sync", "body": "Go"}
        },
        headers=auth_headers_org_a
    )
    assert sched_resp.status_code == 201
    sched_data = sched_resp.json()
    assert sched_data["name"] == "Hourly Sync"
    assert sched_data["cron_expression"] == "0 * * * *"
    sched_id = sched_data["id"]

    # Toggle Schedule
    toggle_resp = client.put(f"/api/v1/schedules/{sched_id}/toggle", json={"is_active": False}, headers=auth_headers_org_a)
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["is_active"] is False

    # Delete Schedule
    delete_resp = client.delete(f"/api/v1/schedules/{sched_id}", headers=auth_headers_org_a)
    assert delete_resp.status_code == 204



def test_ai_failure_summary_endpoint(client, auth_headers_org_a, db):
    # Create project and queue
    proj = client.post("/api/v1/projects", json={"name": "Diagnostic Proj"}, headers=auth_headers_org_a).json()
    queue = client.post(
        f"/api/v1/projects/{proj['id']}/queues",
        json={"name": "diag-queue", "priority": 10},
        headers=auth_headers_org_a
    ).json()

    # Enqueue job
    job_resp = client.post(
        "/api/v1/jobs",
        json={"task_name": "random_fail", "queue_id": queue["id"]},
        headers=auth_headers_org_a
    ).json()
    job_id = job_resp["id"]

    # Retrieve AI summary before failures
    summary_resp = client.get(f"/api/v1/jobs/{job_id}/ai-summary", headers=auth_headers_org_a)
    assert summary_resp.status_code == 200
    assert "Successful" in summary_resp.json()["ai_summary"]

    # Inject simulated failure execution
    from app.models.job import JobExecution
    import uuid
    from datetime import datetime, timezone
    
    db_exec = JobExecution(
        job_id=uuid.UUID(job_id),
        status="failed",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        error="Connection refused: connection to SMTP server failed."
    )
    db.add(db_exec)
    db.commit()

    # Retrieve diagnostic summary after failure
    summary_resp2 = client.get(f"/api/v1/jobs/{job_id}/ai-summary", headers=auth_headers_org_a)
    assert summary_resp2.status_code == 200
    assert "Network Connection" in summary_resp2.json()["ai_summary"]

