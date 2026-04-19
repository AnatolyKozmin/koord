"""Метаданные листа «Домашки» (ИДЗ): индексы колонок по кэшу."""

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import get_current_user
from app.config import get_settings
from app.constants.domashki import map_headers
from app.services import sheets_service

router = APIRouter(prefix="/domashki", tags=["domashki"])


@router.get("/column-layout")
def column_layout(user: dict = Depends(get_current_user)) -> dict:
    _ = user
    sheet = get_settings().sheet_name_domashki
    rows = sheets_service.read_sheet_cached(sheet)
    if not rows or not rows[0]:
        raise HTTPException(
            status_code=404,
            detail=f"Нет данных листа «{sheet}» в кэше — выполните синхронизацию на дашборде.",
        )
    header = rows[0]
    m = map_headers(header)

    def cell_title(idx: int | None) -> str | None:
        if idx is None or idx >= len(header):
            return None
        return str(header[idx]) if header[idx] is not None else None

    return {
        "sheet": sheet,
        "score_column_indices": [{"index": i, "header": cell_title(i)} for i in m.score_cols],
        "sum_column": {"index": m.sum_col, "header": cell_title(m.sum_col)},
        "level_column": {"index": m.level_col, "header": cell_title(m.level_col)},
        "reviewer_questions_column": {
            "index": m.reviewer_questions_col,
            "header": cell_title(m.reviewer_questions_col),
        },
        "reviewer_comment_column": {
            "index": m.reviewer_comment_col,
            "header": cell_title(m.reviewer_comment_col),
        },
    }
