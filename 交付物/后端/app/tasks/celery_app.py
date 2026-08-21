"""Celery 应用入口。"""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "financial_review",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    task_track_started=True,
    task_default_queue="financial-review",
    timezone="Asia/Shanghai",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_soft_time_limit=settings.celery_task_timeout_seconds,
    task_time_limit=settings.celery_task_timeout_seconds + 30,
    worker_prefetch_multiplier=1,
    task_routes={
        "financial_review.analysis_task": {"queue": "financial-review"},
        "financial_review.attachment_parse": {"queue": "financial-review"},
        "financial_review.report_export": {"queue": "financial-review"},
    },
    imports=("app.tasks.analysis_tasks", "app.tasks.attachment_tasks", "app.tasks.report_tasks"),
)
