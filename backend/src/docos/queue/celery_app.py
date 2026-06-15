"""Celery application. Redis is both broker and result backend."""

from __future__ import annotations

from celery import Celery

from docos.settings import get_settings

_settings = get_settings()

celery_app = Celery(
    "docos",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
    include=["docos.queue.tasks"],
)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
