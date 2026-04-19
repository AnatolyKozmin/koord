"""
Подтягивание полей проверяющего с листов «Анкеты» и «Домашки» по email кандидата (кэш Redis).
"""

from __future__ import annotations

from typing import Any

from app.constants.ankety import find_col, map_headers as ankety_map_headers
from app.constants.ankety import HEADER_REVIEWER_COMMENT as A_COMMENT
from app.constants.ankety import HEADER_REVIEWER_QUESTIONS as A_QUESTIONS
from app.constants.domashki import map_headers as domashki_map_headers
from app.constants.domashki import HEADER_REVIEWER_COMMENT as D_COMMENT
from app.constants.domashki import HEADER_REVIEWER_QUESTIONS as D_QUESTIONS


def _row_cell(row: list[Any], c: int | None) -> str:
    """Значение ячейки в одной строке листа (индекс колонки 0-based)."""
    if c is None or c < 0 or c >= len(row):
        return ""
    v = row[c]
    return "" if v is None else str(v).strip()


def normalize_email(raw: str) -> str:
    s = str(raw or "").strip().lower()
    if s.startswith("mailto:"):
        s = s[7:].split("?")[0]
    return s


def candidate_email_from_interview_meta(meta: list[dict[str, Any]]) -> str | None:
    """Email из меты листа «Собес» (строки Gmail / почта)."""
    for m in meta:
        lbl = str(m.get("label", "")).lower()
        val = str(m.get("value", "")).strip()
        if not val:
            continue
        if "@" in val:
            return val
        if "gmail" in lbl or "почт" in lbl or "mail" in lbl:
            return val
    return None


def _find_email_col(header: list[Any]) -> int | None:
    for title in (
        "Почта gmail-",
        "Почта gmail",
        "gmail-почта",
        "Почта Gmail-",
        "Почта",
    ):
        idx = find_col(header, title)
        if idx is not None:
            return idx
    from app.constants.ankety import _norm

    for i, h in enumerate(header):
        if h is None:
            continue
        t = _norm(str(h))
        if "gmail" in t or t.startswith("почт"):
            return i
    from app.constants.domashki import _norm as dn

    for i, h in enumerate(header):
        if h is None:
            continue
        t = dn(str(h))
        if "gmail" in t or "почт" in t:
            return i
    return None


def _find_row_by_email(values: list[list[Any]], email: str) -> int | None:
    if not values or len(values) < 2:
        return None
    want = normalize_email(email)
    if not want or "@" not in want:
        return None
    header = values[0]
    ec = _find_email_col(header)
    if ec is None:
        return None
    for ri in range(1, len(values)):
        got = normalize_email(_row_cell(values[ri], ec))
        if got == want:
            return ri
    return None


def _ankety_external(values: list[list[Any]], email: str) -> dict[str, Any]:
    sheet = "Анкеты"
    if not values or not values[0]:
        return {"matched": False, "sheet": sheet, "reason": "no_cache"}
    header = values[0]
    ri = _find_row_by_email(values, email)
    if ri is None:
        return {"matched": False, "sheet": sheet, "reason": "row_not_found"}
    m = ankety_map_headers(header)
    row = values[ri]
    rq = _row_cell(row, m.reviewer_questions_col)
    rc = _row_cell(row, m.reviewer_comment_col)
    return {
        "matched": True,
        "sheet": sheet,
        "row_index": ri,
        "reviewer_questions": rq,
        "reviewer_comment": rc,
        "columns": {
            "reviewer_questions": A_QUESTIONS,
            "reviewer_comment": A_COMMENT,
        },
    }


def _domashki_external(values: list[list[Any]], email: str) -> dict[str, Any]:
    sheet_label = "Домашки"
    if not values or not values[0]:
        return {"matched": False, "sheet": sheet_label, "reason": "no_cache"}
    header = values[0]
    if _find_email_col(header) is None:
        return {"matched": False, "sheet": sheet_label, "reason": "no_email_column"}

    ri = _find_row_by_email(values, email)
    if ri is None:
        return {"matched": False, "sheet": sheet_label, "reason": "row_not_found"}

    m = domashki_map_headers(header)
    row = values[ri]
    rq = _row_cell(row, m.reviewer_questions_col)
    rc = _row_cell(row, m.reviewer_comment_col)
    return {
        "matched": True,
        "sheet": sheet_label,
        "row_index": ri,
        "reviewer_questions": rq,
        "reviewer_comment": rc,
        "columns": {
            "reviewer_questions": D_QUESTIONS,
            "reviewer_comment": D_COMMENT,
        },
    }


def attach_external_reviews(
    candidate_payload: dict[str, Any],
    ankety_values: list[list[Any]] | None,
    domashki_values: list[list[Any]] | None,
) -> None:
    """Дополняет payload кандидата полями external (мутирует dict)."""
    meta = candidate_payload.get("meta") or []
    email = candidate_email_from_interview_meta(meta)

    out: dict[str, Any] = {
        "candidate_email": email,
        "ankety": {"matched": False, "reason": "no_email_in_meta"},
        "domashki": {"matched": False, "reason": "no_email_in_meta"},
    }

    if email:
        out["ankety"] = _ankety_external(ankety_values or [], email)
        out["domashki"] = _domashki_external(domashki_values or [], email)
    else:
        out["ankety"] = {"matched": False, "reason": "no_email_in_meta"}
        out["domashki"] = {"matched": False, "reason": "no_email_in_meta"}

    candidate_payload["external"] = out
