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
    # Individual task time limits: SIGTERM at 5 min, SIGKILL at 6 min.
    # These fire automatically per task; the watchdog below is a belt-and-suspenders backstop.
    task_soft_time_limit=300,
    task_time_limit=360,
    task_routes={
        "app.workers.tasks.recompute_scores":    {"queue": "scoring"},
        "app.workers.tasks.compute_embeddings":  {"queue": "embeddings"},
        "app.workers.tasks.expire_offers":        {"queue": "maintenance"},
        "app.workers.tasks.watchdog_stuck_tasks": {"queue": "maintenance"},
        "app.workers.tasks.purge_withdrawn":      {"queue": "maintenance"},
    },
    beat_schedule={
        "expire-offers-hourly": {
            "task": "app.workers.tasks.expire_offers",
            "schedule": 3600,
        },
        "purge-withdrawn-daily": {
            "task": "app.workers.tasks.purge_withdrawn",
            "schedule": 86400,
        },
        "watchdog-stuck-tasks": {
            "task": "app.workers.tasks.watchdog_stuck_tasks",
            "schedule": 300,  # every 5 min
        },
    },
)
