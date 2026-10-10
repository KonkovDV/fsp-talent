from celery import Celery
from celery.schedules import crontab

from app.core.config import settings


def demo_reset_entry() -> dict | None:
    """The nightly jury reset, or nothing when the stand is not a demo or the cron is empty."""
    expr = (settings.DEMO_RESET_CRON or "").strip()
    if not settings.DEMO_MODE or not expr:
        return None
    minute, hour, day, month, dow = expr.split()
    return {
        "task": "app.workers.tasks.reset_demo",
        "schedule": crontab(
            minute=minute, hour=hour, day_of_month=day, month_of_year=month, day_of_week=dow,
        ),
    }


def beat_schedule() -> dict:
    schedule = {
        "expire-offers-hourly": {
            "task": "app.workers.tasks.expire_offers",
            "schedule": 3600,
        },
        "task-of-the-week": {
            "task": "app.workers.tasks.offer_weekly_tasks",
            "schedule": crontab(hour=10, minute=0, day_of_week="mon"),   # Moscow time, see timezone
        },
        "purge-withdrawn-daily": {
            "task": "app.workers.tasks.purge_withdrawn",
            "schedule": 86400,
        },
        "purge-guests-hourly": {
            "task": "app.workers.tasks.purge_guests",
            "schedule": 3600,
        },
        "watchdog-stuck-tasks": {
            "task": "app.workers.tasks.watchdog_stuck_tasks",
            "schedule": 300,  # every 5 min
        },
        "sync-fsp-changes-hourly": {
            "task": "app.workers.tasks.sync_fsp_changes",
            "schedule": 3600,
        },
        "deliver-webhooks": {
            "task": "app.workers.tasks.deliver_webhooks",
            "schedule": 60,
        },
        "grade-fail-rates-nightly": {
            "task": "app.workers.tasks.refresh_grade_fail_rates",
            "schedule": crontab(hour=3, minute=40),
        },
    }
    reset = demo_reset_entry()
    if reset is not None:
        schedule["demo-reset-nightly"] = reset
    return schedule


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
    # These fire automatically per task; the watchdog below is a backstop for a task that ignores signals.
    task_soft_time_limit=300,
    task_time_limit=360,
    task_routes={
        "app.workers.tasks.recompute_scores":    {"queue": "scoring"},
        "app.workers.tasks.compute_embeddings":  {"queue": "embeddings"},
        "app.workers.tasks.expire_offers":        {"queue": "maintenance"},
        "app.workers.tasks.watchdog_stuck_tasks": {"queue": "maintenance"},
        "app.workers.tasks.purge_withdrawn":      {"queue": "maintenance"},
        "app.workers.tasks.purge_guests":         {"queue": "maintenance"},
        "app.workers.tasks.offer_weekly_tasks":   {"queue": "maintenance"},
        "app.workers.tasks.sync_fsp_changes":     {"queue": "maintenance"},
        "app.workers.tasks.reset_demo":          {"queue": "maintenance"},
        "app.workers.tasks.refresh_grade_fail_rates": {"queue": "maintenance"},
        "app.workers.tasks.deliver_webhooks": {"queue": "maintenance"},
    },
    beat_schedule=beat_schedule(),
)
