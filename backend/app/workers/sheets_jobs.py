"""
Задачи RQ: запись в Google Sheets.

Воркер `rq worker sheets` обрабатывает задачи **последовательно** (один воркер = один поток
запросов к API), плюс пауза между задачами и повтор при 429/503 — укладываемся в лимиты Sheets API.
"""

from __future__ import annotations

import random
import time
from typing import Any

from app.config import get_settings


def apply_values_update(range_a1: str, values: list[list[Any]]) -> dict[str, Any]:
    settings = get_settings()
    sid = settings.google_spreadsheet_id
    creds_path = settings.google_application_credentials
    if not sid or not creds_path:
        return {"ok": False, "error": "Sheets not configured"}

    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=scopes,
    )
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)

    body = {"values": values}
    max_retries = max(1, settings.google_sheets_write_max_retries)

    for attempt in range(max_retries):
        try:
            service.spreadsheets().values().update(
                spreadsheetId=sid,
                range=range_a1,
                valueInputOption="USER_ENTERED",
                body=body,
            ).execute()
            break
        except HttpError as e:
            status = e.resp.status if e.resp is not None else 0
            if status in (429, 503) and attempt < max_retries - 1:
                base = 0.5 * (2**attempt)
                jitter = random.uniform(0, 0.3)
                time.sleep(min(base + jitter, 60.0))
                continue
            raise

    time.sleep(max(0.0, settings.google_sheets_write_interval_sec))
    return {"ok": True, "range": range_a1}


def apply_batch_values_update(
    updates: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Один запрос spreadsheets.values.batchUpdate на несколько диапазонов
    (меньше нагрузка на API, чем отдельные update по ячейке).
    """
    settings = get_settings()
    sid = settings.google_spreadsheet_id
    creds_path = settings.google_application_credentials
    if not sid or not creds_path:
        return {"ok": False, "error": "Sheets not configured"}

    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=scopes,
    )
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)

    body = {
        "valueInputOption": "USER_ENTERED",
        "data": [{"range": u["range_a1"], "values": u["values"]} for u in updates],
    }
    
    max_retries = max(1, settings.google_sheets_write_max_retries)

    for attempt in range(max_retries):
        try:
            service.spreadsheets().values().batchUpdate(spreadsheetId=sid, body=body).execute()
            break
        except HttpError as e:
            status = e.resp.status if e.resp is not None else 0
            if status in (429, 503) and attempt < max_retries - 1:
                base = 0.5 * (2**attempt)
                jitter = random.uniform(0, 0.3)
                time.sleep(min(base + jitter, 60.0))
                continue
            raise

    time.sleep(max(0.0, settings.google_sheets_write_interval_sec))
    return {"ok": True, "ranges": len(updates)}
