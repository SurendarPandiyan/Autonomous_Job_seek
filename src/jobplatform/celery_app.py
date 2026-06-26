from celery import Celery

from jobplatform.config import settings

celery_app: Celery = Celery(
    "jobplatform",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["jobplatform.jobs.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "jobplatform.jobs.tasks.scrape_portal": {"queue": "scraper"},
    },
)
