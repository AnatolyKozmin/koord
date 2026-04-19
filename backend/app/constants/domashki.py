"""
Структура листа «Домашки» (ИДЗ) в Google Sheets.
Блок баллов: от «Заинтересованность» до «Характеристика X», затем сумма, уровень, вопросы и комментарий проверяющего.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Баллы (8 столбцов) — как в вашей шапке таблицы
DOMASHKI_SCORE_HEADERS: tuple[str, ...] = (
    "Заинтересованность",
    "Креативное мышление",
    "Понимание ССт",
    "Соблюдение ДД",
    "Наличие опыта в похожей деятельности",
    "Мотивация",
    "Девиантность (Маркер)",
    "Характеристика X",
)

HEADER_SUM = "Общая оценка по ИДЗ"

HEADER_LEVEL = "Уровень по итогам ИДЗ"

HEADER_REVIEWER_QUESTIONS = "Вопросы по ИДЗ (если вопросов нет, так и пишите)"

HEADER_REVIEWER_COMMENT = "Комментарий по ИДЗ"


def _norm(s: str) -> str:
    return " ".join(s.replace("\r", "").split()).strip().lower()


def find_col(header_row: list[Any], title: str) -> int | None:
    want = _norm(title)
    for i, cell in enumerate(header_row):
        if cell is None:
            continue
        if _norm(str(cell)) == want:
            return i
    return None


@dataclass(frozen=True)
class DomashkiColumnMap:
    score_cols: tuple[int, ...]
    sum_col: int | None
    level_col: int | None
    reviewer_questions_col: int | None
    reviewer_comment_col: int | None


def map_headers(header_row: list[Any]) -> DomashkiColumnMap:
    scores: list[int] = []
    for h in DOMASHKI_SCORE_HEADERS:
        idx = find_col(header_row, h)
        if idx is not None:
            scores.append(idx)
    return DomashkiColumnMap(
        score_cols=tuple(scores),
        sum_col=find_col(header_row, HEADER_SUM),
        level_col=find_col(header_row, HEADER_LEVEL),
        reviewer_questions_col=find_col(header_row, HEADER_REVIEWER_QUESTIONS),
        reviewer_comment_col=find_col(header_row, HEADER_REVIEWER_COMMENT),
    )
