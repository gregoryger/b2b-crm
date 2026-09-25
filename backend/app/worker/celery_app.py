from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery = Celery("crm", broker=settings.REDIS_URL, backend=settings.REDIS_URL, include=["app.worker.tasks"])
celery.conf.update(
    timezone=settings.TIMEZONE,
    enable_utc=True,
    task_always_eager=settings.CELERY_ALWAYS_EAGER,
    task_eager_propagates=False,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_default_retry_delay=30,
    beat_schedule={
        "reminders": {"task": "app.worker.tasks.process_reminders", "schedule": 60.0},
        "imap-leads": {"task": "app.worker.tasks.poll_imap", "schedule": 120.0},
        "telegram-updates": {"task": "app.worker.tasks.poll_telegram", "schedule": 20.0},
        "stale-deals": {"task": "app.worker.tasks.stale_deals_digest", "schedule": crontab(hour=9, minute=0)},
        "scheduled-reports": {"task": "app.worker.tasks.send_scheduled_reports",
                              "schedule": crontab(hour=7, minute=30)},
    },
)
