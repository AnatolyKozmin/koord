"""Метаданные листа «Анкеты»: сопоставление заголовков с индексами колонок (по кэшу)."""

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import get_current_user
from app.config import get_settings
from app.constants.ankety import (
    ANKETY_SCORE_OPTIONS,
    ANKETY_SCORE_OPTIONS_DEFAULT,
    map_headers,
)
from app.services import sheets_service

router = APIRouter(prefix="/ankety", tags=["ankety"])


@router.get("/column-layout")
def column_layout(user: dict = Depends(get_current_user)) -> dict:
    """
    По первой строке кэшированного листа «Анкеты»: индексы колонок для баллов,
    суммы, уровня, вопросов и комментария проверяющего.
    """
    _ = user
    sheet = get_settings().sheet_name_ankety
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

    def score_options(raw_header: str | None) -> list[str]:
        """Допустимые баллы для конкретного маркера."""
        if not raw_header:
            return list(ANKETY_SCORE_OPTIONS_DEFAULT)
        from app.constants.ankety import _norm
        key = _norm(raw_header)
        for h, opts in ANKETY_SCORE_OPTIONS.items():
            if _norm(h) == key:
                return list(opts)
        return list(ANKETY_SCORE_OPTIONS_DEFAULT)

    return {
        "sheet": sheet,
        "score_column_indices": [
            {"index": i, "header": cell_title(i), "options": score_options(cell_title(i))}
            for i in m.score_cols
        ],
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
