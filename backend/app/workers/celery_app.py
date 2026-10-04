from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "fsp_talent",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_routes={
        "app.workers.tasks.recompute_scores": {"queue": "scoring"},
        "app.workers.tasks.compute_embeddings": {"queue": "embeddings"},
        "app.workers.tasks.expire_offers": {"queue": "maintenance"},
    },
    beat_schedule={
        "expire-offers-hourly": {
            "task": "app.workers.tasks.expire_offers",
            "schedule": 3600,
        },
    },
)
