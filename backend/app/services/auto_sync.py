"""Фоновый таск: периодически синхронизирует листы Google и инкрементально раздаёт новые строки.

Запускается через FastAPI lifespan, если AUTO_SYNC_INTERVAL_SEC > 0.
Раздаёт только тем проверяющим, у кого в БД есть непустой reviewer_faculties.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import select

from app.config import get_settings
from app.db.models import User, UserReviewerFaculty
from app.db.session import SessionLocal
from app.services import assignments_service, sheets_service

log = logging.getLogger("uvicorn.error")


def _eligible_reviewer_emails() -> list[str]:
    """Список email проверяющих с хотя бы одним allowed faculty (участников автораздачи)."""
    with SessionLocal() as session:
        rows = session.execute(
            select(User.email)
            .join(UserReviewerFaculty, UserReviewerFaculty.user_id == User.id)
            .where(User.role == "user")
            .distinct(),
        ).all()
    return sorted({r[0].lower() for r in rows if r and r[0]})


def _do_one_pass() -> dict[str, Any]:
    """Одна итерация: синхронизация + инкрементальное распределение анкет и домашек."""
    settings = get_settings()
    fetched = sheets_service.fetch_and_cache_all()
    note: dict[str, Any] = {"sheets_fetched": list(fetched.keys())}

    emails = _eligible_reviewer_emails()
    if not emails:
        note["skip"] = "Нет проверяющих с настроенными reviewer_faculties — нечего распределять."
        return note

    try:
        ank = assignments_service.distribute_anketa_balanced_by_faculty_incremental(
            settings.sheet_name_ankety,
            emails,
        )
        note["ankety"] = {
            "newly": sum(len(v) for v in ank.get("newly_assigned", {}).values()),
            "unassigned": len(ank.get("unassigned", [])),
        }
    except ValueError as e:
        note["ankety_skip"] = str(e)

    try:
        dom = assignments_service.distribute_domashki_balanced_by_faculty(
            settings.sheet_name_domashki,
            emails,
        )
        note["domashki"] = {
            "newly": sum(len(v) for v in dom.get("newly_assigned", {}).values()),
            "unassigned": len(dom.get("unassigned", [])),
        }
    except ValueError as e:
        note["domashki_skip"] = str(e)

    return note


async def auto_sync_loop(interval_sec: int) -> None:
    log.info("auto_sync: started, interval=%ss", interval_sec)
    try:
        while True:
            try:
                result = await asyncio.to_thread(_do_one_pass)
                log.info("auto_sync: pass done %s", result)
            except Exception as exc:  # noqa: BLE001
                log.warning("auto_sync: pass failed: %s", exc)
            await asyncio.sleep(interval_sec)
    except asyncio.CancelledError:
        log.info("auto_sync: stopped")
        raise
