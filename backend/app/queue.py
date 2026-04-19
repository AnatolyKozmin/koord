"""Очередь RQ для записи в Google Sheets (сглаживание лимитов API)."""

from redis import Redis
from rq import Queue

from app.config import get_settings


def get_sheets_queue() -> Queue:
    settings = get_settings()
    r = Redis.from_url(settings.redis_url)
    return Queue(settings.rq_queue_name, connection=r)
