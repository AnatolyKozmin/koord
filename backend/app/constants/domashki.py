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

# Поле студенческого билета — по нему ищем факультет в листе «Анкеты»
DOMASHKI_STUDENT_ID_HEADER = "Номер студенческого билета"


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


def find_header_row(all_rows: list[list[Any]]) -> list[Any]:
    """Возвращает строку заголовков из листа Домашка.

    Лист может иметь двойную шапку (строка 1 — объединённый заголовок-заглушка,
    строка 2 — реальные названия колонок). Проверяем обе строки: берём ту,
    в которой находится хотя бы один из ожидаемых заголовков баллов.
    """
    for row in all_rows[:3]:
        if any(find_col(row, h) is not None for h in DOMASHKI_SCORE_HEADERS):
            return row
    return all_rows[0] if all_rows else []


def data_start_index(all_rows: list[list[Any]]) -> int:
    """Индекс первой строки данных (после всех строк заголовков)."""
    for i, row in enumerate(all_rows[:3]):
        if any(find_col(row, h) is not None for h in DOMASHKI_SCORE_HEADERS):
            return i + 1
    return 1


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
