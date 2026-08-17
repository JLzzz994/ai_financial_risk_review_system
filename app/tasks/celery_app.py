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
)
