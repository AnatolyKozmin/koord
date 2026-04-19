"""Разбор листа «Собеседования»: шаблон по строкам + значения в колонке кандидата."""

from __future__ import annotations

from typing import Any

from app.constants.sobesedovaniya import (
    cell,
    find_questions_header_row,
    find_score_block_start_row,
)


def _meta_rows_before(values: list[list[Any]], end_row: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in range(0, max(0, end_row)):
        label = cell(values, r, 0).strip()
        if not label:
            continue
        out.append({"row": r, "label": label})
    return out


def _question_rows(
    values: list[list[Any]],
    start: int,
    end: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in range(start, end):
        key = cell(values, r, 0).strip()
        extra = cell(values, r, 1).strip()
        q = cell(values, r, 2).strip()
        if not key and not extra and not q:
            continue
        out.append(
            {
                "row": r,
                "key_characteristic": key,
                "extra_characteristic": extra,
                "question": q,
            }
        )
    return out


def _score_rows(values: list[list[Any]], start: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in range(start, len(values)):
        label = cell(values, r, 0).strip()
        if not label:
            continue
        out.append({"row": r, "label": label})
    return out


def build_candidate_payload(
    values: list[list[Any]],
    candidate_col: int,
) -> dict[str, Any]:
    """
    candidate_col — индекс колонки с ответами/баллами по кандидату (часто D = 3).
    Колонки 0–2 — шаблон вопросов; мета и баллы читаются из candidate_col.
    """
    qh = find_questions_header_row(values)
    if qh is None:
        return {
            "column_index": candidate_col,
            "parse_ok": False,
            "error": "Не найдена строка шапки «Ключевая характеристика / Вопрос».",
            "meta": [],
            "questions": [],
            "scores": [],
        }

    ss = find_score_block_start_row(values, qh)
    if ss is None:
        ss = len(values)

    meta_template = _meta_rows_before(values, qh)
    meta: list[dict[str, Any]] = []
    for m in meta_template:
        r = m["row"]
        lbl = str(m["label"])
        val = cell(values, r, candidate_col).strip()
        meta.append({"row": r, "label": lbl, "value": val})

    questions = _question_rows(values, qh + 1, ss)
    for q in questions:
        q["answer"] = cell(values, q["row"], candidate_col).strip()

    score_defs = _score_rows(values, ss)
    scores: list[dict[str, Any]] = []
    for s in score_defs:
        r = s["row"]
        lbl = s["label"]
        scores.append(
            {
                "row": r,
                "label": lbl,
                "value": cell(values, r, candidate_col).strip(),
            }
        )

    return {
        "column_index": candidate_col,
        "parse_ok": True,
        "questions_header_row": qh,
        "score_block_start_row": ss,
        "meta": meta,
        "questions": questions,
        "scores": scores,
    }


def sheet_max_column_index(values: list[list[Any]]) -> int:
    return max((len(r) for r in values), default=0)
