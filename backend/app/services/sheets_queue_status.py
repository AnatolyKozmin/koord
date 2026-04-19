"""Статус задач RQ для записи в Google Sheets."""

from __future__ import annotations

from typing import Any

from redis import Redis
from rq.exceptions import NoSuchJobError
from rq.job import Job

from app.config import get_settings


def get_job_payload(job_id: str) -> dict[str, Any]:
    settings = get_settings()
    conn = Redis.from_url(settings.redis_url)
    try:
        job = Job.fetch(job_id, connection=conn)
    except NoSuchJobError as e:
        raise KeyError(job_id) from e

    status = job.get_status()
    out: dict[str, Any] = {
        "job_id": job_id,
        "status": status,
        "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
        "ended_at": job.ended_at.isoformat() if job.ended_at else None,
    }
    if job.is_finished:
        out["result"] = job.result
    if job.is_failed:
        out["error"] = job.exc_info
    return out
