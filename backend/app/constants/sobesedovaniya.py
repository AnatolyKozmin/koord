"""
Структура листа «Собеседования» (вертикальный шаблон).

Первая колонка (A) — подписи строк: мета, затем блок вопросов (ключ / доп / текст в колонках A–C),
ниже — блок оценок. Значения по кандидатам — начиная с настраиваемой колонки (по умолчанию D, индекс 3).
"""

from __future__ import annotations

from typing import Any

# Строка-шапка блока вопросов (поиск по первым трём колонкам)
HEADER_QUESTIONS_A = "Ключевая характеристика"
HEADER_QUESTIONS_B = "Доп. характеристика"
HEADER_QUESTIONS_C = "Вопрос"

# Начало блока баллов (по первой колонке)
MARKER_SCORE_BLOCK = "оценка кандидата"

def _norm(s: str) -> str:
    return " ".join(s.replace("\r", "").split()).strip().lower()


def cell(values: list[list[Any]], r: int, c: int) -> str:
    if r < 0 or r >= len(values):
        return ""
    row = values[r]
    if c < 0 or c >= len(row):
        return ""
    v = row[c]
    return "" if v is None else str(v)


def find_questions_header_row(values: list[list[Any]]) -> int | None:
    """Строка с «Ключевая характеристика» | «Доп. характеристика» | «Вопрос»."""
    for i, row in enumerate(values):
        a = _norm(cell(values, i, 0))
        b = _norm(cell(values, i, 1))
        c = _norm(cell(values, i, 2))
        if HEADER_QUESTIONS_A.lower() in a or _norm(HEADER_QUESTIONS_A) == a:
            if "доп" in b and "характеристик" in b:
                if "вопрос" in c:
                    return i
        if _norm(HEADER_QUESTIONS_A) in a and "вопрос" in c:
            return i
    return None


def find_score_block_start_row(values: list[list[Any]], after_row: int) -> int | None:
    """Первая строка блока оценок (ячейка A содержит «Оценка кандидата» или похожее)."""
    for i in range(max(0, after_row + 1), len(values)):
        a = _norm(cell(values, i, 0))
        if not a:
            continue
        if MARKER_SCORE_BLOCK in a or "оценка кандидата" in a:
            return i
        if "заинтересованность" in a and "сквозн" in a:
            return i
    return None
