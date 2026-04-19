"""Лист «Собеседования»: вертикальный шаблон, кандидаты по колонкам."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.deps import get_current_user
from app.config import get_settings
from app.services import assignments_service, sheets_service
from app.services.interviews_external import attach_external_reviews
from app.services.interviews_layout import build_candidate_payload, sheet_max_column_index
from app.utils.sheets_a1 import col_index_to_letters, quote_sheet_name

router = APIRouter(prefix="/interviews", tags=["interviews"])


class InterviewCell(BaseModel):
    row: int = Field(ge=0, description="Индекс строки в листе, 0-based")
    value: str = ""


class InterviewSaveBody(BaseModel):
    column_index: int = Field(ge=0)
    cells: list[InterviewCell]


def _candidate_columns_for_user(user: dict) -> list[int] | None:
    """None — супер-админ: все колонки кандидатов по ширине листа."""
    settings = get_settings()
    sheet = settings.sheet_name_interviews
    rows = sheets_service.read_sheet_cached(sheet)
    if not rows:
        return []
    fc = settings.sheet_interviews_first_candidate_col_index
    max_w = sheet_max_column_index(rows)
    all_cols = list(range(fc, max_w))

    if user.get("role") == "super_admin":
        return all_cols

    email = user.get("email", "")
    allowed = sorted(
        set(assignments_service.get_assignment(email).get(sheet, [])),
    )
    return [c for c in allowed if fc <= c < max_w]


@router.get("/payload")
def interviews_payload(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    settings = get_settings()
    sheet = settings.sheet_name_interviews
    rows = sheets_service.read_sheet_cached(sheet)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Нет данных листа «{sheet}» в кэше — выполните синхронизацию.",
        )

    cols = _candidate_columns_for_user(user)
    candidates = [build_candidate_payload(rows, c) for c in cols]

    ankety_vals = sheets_service.read_sheet_cached(settings.sheet_name_ankety)
    domashki_vals = sheets_service.read_sheet_cached(settings.sheet_name_domashki)
    for cand in candidates:
        attach_external_reviews(cand, ankety_vals, domashki_vals)

    return {
        "sheet": sheet,
        "first_candidate_col_index": settings.sheet_interviews_first_candidate_col_index,
        "candidates": candidates,
    }


@router.post("/save")
def interviews_save(body: InterviewSaveBody, user: dict = Depends(get_current_user)) -> dict[str, str]:
    settings = get_settings()
    sheet = settings.sheet_name_interviews
    if user.get("role") != "super_admin":
        allowed = set(assignments_service.get_assignment(user.get("email", "")).get(sheet, []))
        if body.column_index not in allowed:
            raise HTTPException(status_code=403, detail="Нет доступа к этой колонке кандидата.")

    if not body.cells:
        raise HTTPException(status_code=400, detail="Список ячеек пуст")

    q = quote_sheet_name(sheet)
    letters = col_index_to_letters(body.column_index)
    updates: list[dict[str, Any]] = []
    for c in body.cells:
        row_1based = c.row + 1
        updates.append(
            {
                "range_a1": f"{q}!{letters}{row_1based}",
                "values": [[c.value]],
            },
        )

    job_id = sheets_service.enqueue_batch_values_update(updates)
    return {"job_id": job_id, "status": "queued", "poll_url": f"/api/sheets/queue/status/{job_id}"}
