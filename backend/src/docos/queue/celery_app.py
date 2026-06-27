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
# When eager (the offline/dev/test default) any ``.delay()`` runs inline. The async upload route
# deliberately avoids ``.delay()`` in eager mode, but keeping this aligned with the setting means a
# stray enqueue in tests still runs in-process instead of trying to reach Redis.
celery_app.conf.task_always_eager = _settings.celery_eager
