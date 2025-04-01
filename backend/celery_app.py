# backend/celery_app.py
from celery import Celery
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.scanpy_tasks",
        "app.tasks.integration_tasks",  # NEW
        "app.tasks.trajectory_tasks",   # NEW
        "app.tasks.communication_tasks",# NEW
        ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Increase visibility timeout if CPDB tasks are very long?
    # broker_transport_options = {'visibility_timeout': 7200} # e.g., 2 hours
)