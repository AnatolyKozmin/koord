"""Статистика: кэш листов в Redis; пользователи и назначения — в SQL; сводка по мастерам — БД + кэш."""

import json

from fastapi import APIRouter, Depends

from app.auth.deps import get_current_user
from app.config import get_settings
from app.redis_client import get_redis
from app.services import master_stats
from app.services.sheets_service import META_KEY, SNAPSHOT_KEY

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/sheet-names")
def sheet_tab_names(user: dict = Depends(get_current_user)) -> dict[str, str]:
    """Имена вкладок Google Таблицы из .env — для фронта и проверки конфигурации."""
    _ = user
    s = get_settings()
    return {
        "subs": s.sheet_name_subs,
        "enquiries": s.sheet_name_enquiries,
        "domashki": s.sheet_name_domashki,
        "ankety": s.sheet_name_ankety,
        "interviews": s.sheet_name_interviews,
    }


@router.get("/master-dashboard")
def master_dashboard_stats(user: dict = Depends(get_current_user)) -> dict:
    """
    Сводка по мастерам: назначения из БД, проверено/остаток — по данным кэша листов после синхронизации.
    Супер-админ видит всех; проверяющий — только свою строку.
    """
    data = master_stats.master_dashboard()
    if user.get("role") != "super_admin":
        em = (user.get("email") or "").lower()
        data["masters"] = [m for m in data["masters"] if m["email"] == em]
    return data


@router.get("/dashboard")
def dashboard(user: dict = Depends(get_current_user)) -> dict:
    _ = user
    r = get_redis()
    meta_raw = r.get(META_KEY)
    snap_raw = r.get(SNAPSHOT_KEY)
    meta = json.loads(meta_raw) if meta_raw else {}
    snapshot = json.loads(snap_raw) if snap_raw else {}
    totals = {name: len(rows) for name, rows in snapshot.items()}
    return {"meta": meta, "row_counts": totals, "cached_sheets": list(snapshot.keys())}
