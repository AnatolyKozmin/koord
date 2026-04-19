"""
Чтение/запись Google Sheets. Запись в листы — через постановку задач в RQ (workers/sheets_jobs).
"""

from __future__ import annotations

import json
from typing import Any

from app.config import get_settings
from app.redis_client import get_redis


def default_sheet_tabs() -> tuple[str, ...]:
    s = get_settings()
    return (
        s.sheet_name_subs,
        s.sheet_name_enquiries,
        s.sheet_name_domashki,
        s.sheet_name_ankety,
        s.sheet_name_interviews,
    )


def _client():
    settings = get_settings()
    if not settings.google_application_credentials or not settings.google_spreadsheet_id:
        return None
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        settings.google_application_credentials,
        scopes=scopes,
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


SNAPSHOT_KEY = "cache:sheets:snapshot"
META_KEY = "cache:sheets:meta"


def read_sheet_cached(sheet_name: str) -> list[list[Any]] | None:
    """Строки листа из Redis-снимка (после синхронизации)."""
    r = get_redis()
    raw = r.get(SNAPSHOT_KEY)
    if not raw:
        return None
    data = json.loads(raw)
    if sheet_name not in data:
        return None
    return data[sheet_name]


def store_snapshot(sheets: dict[str, list[list[Any]]]) -> None:
    """Сохранить снимок листов в Redis (AOF на volume — переживает перезапуск)."""
    r = get_redis()
    pipe = r.pipeline()
    pipe.set(SNAPSHOT_KEY, json.dumps(sheets, default=str))
    pipe.set(META_KEY, json.dumps({"version": 1}))
    pipe.execute()


def fetch_and_cache_all(tab_names: list[str] | None = None) -> dict[str, list[list[Any]]]:
    """
    Прочитать листы из API и обновить кэш.
    Без credentials — сохраняем заглушку, чтобы фронт не падал.
    """
    names = tab_names or list(default_sheet_tabs())
    settings = get_settings()
    out: dict[str, list[list[Any]]] = {}
    service = _client()
    sid = settings.google_spreadsheet_id

    if not service or not sid:
        for name in names:
            out[name] = [["Нет доступа к API"], ["Заполните GOOGLE_* в .env и выполните синхронизацию"]]
        store_snapshot(out)
        return out

    def _tab_titles() -> list[str]:
        try:
            meta = (
                service.spreadsheets()
                .get(spreadsheetId=sid, fields="sheets.properties.title")
                .execute()
            )
            return [str(s["properties"]["title"]) for s in meta.get("sheets", [])]
        except Exception:
            return []

    def _range_a1(sheet_title: str) -> str:
        esc = (sheet_title or "").replace("'", "''")
        return f"'{esc}'!A:ZZ"

    tab_titles_cache: list[str] | None = None

    for name in names:
        try:
            result = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range=_range_a1(name))
                .execute()
            )
            out[name] = result.get("values", [])
        except Exception as exc:  # noqa: BLE001 — логируем проблемный лист
            if tab_titles_cache is None:
                tab_titles_cache = _tab_titles()
            hint = ""
            if tab_titles_cache:
                hint = (
                    " Проверьте SHEET_NAME_* в .env — имя вкладки должно совпадать с таблицей "
                    f"(регистр и символы важны). Вкладки сейчас: {', '.join(repr(t) for t in tab_titles_cache)}."
                )
            out[name] = [["Ошибка чтения"], [str(exc) + hint]]

    store_snapshot(out)
    return out


def enqueue_cells_update(range_a1: str, values: list[list[Any]]) -> str:
    """
    Все записи значений в таблицу — только через эту очередь (Redis + RQ), не вызывать Sheets API из HTTP-запроса.
    Воркер выполняет задачи по одной и выдерживает паузу между вызовами (см. GOOGLE_SHEETS_WRITE_INTERVAL_SEC).
    """
    from app.queue import get_sheets_queue

    q = get_sheets_queue()
    job = q.enqueue(
        "app.workers.sheets_jobs.apply_values_update",
        range_a1,
        values,
        job_timeout=600,
        result_ttl=86400,
    )
    return job.id


def enqueue_batch_values_update(updates: list[dict[str, Any]]) -> str:
    """Пакетная запись нескольких диапазонов одним batchUpdate (очередь RQ)."""
    from app.queue import get_sheets_queue

    if not updates:
        raise ValueError("updates пустой")
    q = get_sheets_queue()
    job = q.enqueue(
        "app.workers.sheets_jobs.apply_batch_values_update",
        updates,
        job_timeout=600,
        result_ttl=86400,
    )
    return job.id
