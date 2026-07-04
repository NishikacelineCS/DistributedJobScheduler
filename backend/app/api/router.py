from fastapi import APIRouter
from app.api.endpoints import auth, tenants, jobs, schedules, workers

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(tenants.router, tags=["projects-queues"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(schedules.router, prefix="/schedules", tags=["schedules"])
api_router.include_router(workers.router, prefix="/workers", tags=["workers"])
