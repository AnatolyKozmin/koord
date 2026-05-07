"""Сводка по мастерам: назначения из БД + статусы из кэша Google Sheets."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.config import get_settings
from app.constants.ankety import map_headers as ankety_map_headers
from app.constants.domashki import (
    DOMASHKI_STUDENT_ID_HEADER,
    data_start_index as domashki_data_start_index,
    find_col as domashki_find_col,
    find_header_row as domashki_find_header_row,
    map_headers as domashki_map_headers,
)
from app.db.models import User
from app.db.session import SessionLocal
from app.services import assignments_service, sheets_service
from app.services.interviews_layout import build_candidate_payload


def _cell(row: list[Any], i: int | None) -> str:
    if i is None or i < 0 or i >= len(row):
        return ""
    v = row[i]
    return "" if v is None else str(v).strip()


def _row_reviewed_generic(
    row: list[Any],
    score_cols: tuple[int, ...],
    comment_col: int | None,
) -> bool:
    for i in score_cols:
        if _cell(row, i):
            return True
    if comment_col is not None and _cell(row, comment_col):
        return True
    return False


def master_dashboard() -> dict[str, Any]:
    """
    Для каждого пользователя с role=user: счётчики по назначенным строкам/колонкам.
    «Проверено» — есть хотя бы один балл или комментарий проверяющего (по разметке листа).
    """
    settings = get_settings()
    ankety_sheet = settings.sheet_name_ankety
    domashki_sheet = settings.sheet_name_domashki
    interviews_sheet = settings.sheet_name_interviews

    ankety_vals = sheets_service.read_sheet_cached(ankety_sheet) or []
    dom_vals = sheets_service.read_sheet_cached(domashki_sheet) or []
    int_vals = sheets_service.read_sheet_cached(interviews_sheet) or []

    ank_header = ankety_vals[0] if ankety_vals else []
    dom_header = domashki_find_header_row(dom_vals) if dom_vals else []
    dom_data_start = domashki_data_start_index(dom_vals) if dom_vals else 1
    dom_sid_col = domashki_find_col(dom_header, DOMASHKI_STUDENT_ID_HEADER) if dom_header else None

    am = ankety_map_headers(ank_header) if ank_header else None
    dm = domashki_map_headers(dom_header) if dom_header else None

    masters: list[dict[str, Any]] = []

    with SessionLocal() as session:
        users = session.scalars(
            select(User)
            .where(User.role == "user")
            .order_by(User.faculty.asc().nulls_last(), User.master_label.asc(), User.email.asc()),
        ).all()
        for idx, u in enumerate(users):
            label = u.master_label or f"Мастер {idx + 1}"
            if u.faculty:
                label = f"{label} · {u.faculty}"
            assign = assignments_service.get_assignment(u.email)

            # Анкеты
            a_total = a_rev = 0
            rows_a = assign.get(ankety_sheet, [])
            if am and ankety_vals:
                for ri in rows_a:
                    if ri < 1 or ri >= len(ankety_vals):
                        continue
                    row = ankety_vals[ri]
                    a_total += 1
                    if _row_reviewed_generic(
                        row,
                        am.score_cols,
                        am.reviewer_comment_col,
                    ):
                        a_rev += 1

            # Домашки
            d_total = d_rev = 0
            rows_d = assign.get(domashki_sheet, [])
            if dm and dom_vals:
                for ri in rows_d:
                    if ri < dom_data_start or ri >= len(dom_vals):
                        continue
                    row = dom_vals[ri]
                    d_total += 1
                    if _row_reviewed_generic(
                        row,
                        dm.score_cols,
                        dm.reviewer_comment_col,
                    ):
                        d_rev += 1

            # Собеседования (колонки)
            iv_total = iv_done = 0
            cols = assign.get(interviews_sheet, [])
            if int_vals:
                for col in cols:
                    p = build_candidate_payload(int_vals, col)
                    if not p.get("parse_ok"):
                        continue
                    iv_total += 1
                    done = False
                    for sc in p.get("scores", []):
                        if str(sc.get("value", "")).strip():
                            done = True
                            break
                    if done:
                        iv_done += 1

            masters.append(
                {
                    "email": u.email,
                    "label": label,
                    "faculty": u.faculty,
                    "ankety": {
                        "total": a_total,
                        "reviewed": a_rev,
                        "pending": max(0, a_total - a_rev),
                    },
                    "domashki": {
                        "total": d_total,
                        "reviewed": d_rev,
                        "pending": max(0, d_total - d_rev),
                    },
                    "interviews": {
                        "total": iv_total,
                        "conducted": iv_done,
                        "pending": max(0, iv_total - iv_done),
                    },
                },
            )

    # Сводка по листам: какие строки данных «потеряны» (есть в листе, но не назначены никому)
    ankety_assigned_map = assignments_service.row_to_reviewer_map(ankety_sheet)
    domashki_assigned_map = assignments_service.row_to_reviewer_map(domashki_sheet)

    ankety_data_indices = list(range(1, len(ankety_vals))) if ankety_vals else []
    domashki_data_indices = list(range(dom_data_start, len(dom_vals))) if dom_vals else []

    ankety_unassigned = [i for i in ankety_data_indices if i not in ankety_assigned_map]
    domashki_unassigned = [i for i in domashki_data_indices if i not in domashki_assigned_map]

    # Домашки без матча по студ. билету в анкетах — их нельзя автораздать
    domashki_no_sid_match = 0
    if dom_vals and dom_sid_col is not None:
        # Карта sid -> faculty из анкет (используем тот же алгоритм, что в распределении)
        sid_to_faculty = assignments_service._build_student_id_to_faculty_map()
        for ri in domashki_data_indices:
            row = dom_vals[ri]
            sid_raw = row[dom_sid_col] if dom_sid_col < len(row) else ""
            sid = str(sid_raw).strip().lower() if sid_raw else ""
            if not sid or sid not in sid_to_faculty:
                domashki_no_sid_match += 1

    sheets_summary = {
        "ankety": {
            "sheet": ankety_sheet,
            "total_rows": len(ankety_data_indices),
            "assigned": len(ankety_data_indices) - len(ankety_unassigned),
            "unassigned_count": len(ankety_unassigned),
            "unassigned_indices": ankety_unassigned[:200],
        },
        "domashki": {
            "sheet": domashki_sheet,
            "total_rows": len(domashki_data_indices),
            "assigned": len(domashki_data_indices) - len(domashki_unassigned),
            "unassigned_count": len(domashki_unassigned),
            "unassigned_indices": domashki_unassigned[:200],
            "no_student_id_match": domashki_no_sid_match,
        },
    }

    cache_ok = bool(ankety_vals or dom_vals or int_vals)
    return {
        "masters": masters,
        "sheets_summary": sheets_summary,
        "cache_loaded": cache_ok,
        "note": None
        if cache_ok
        else "Кэш листов пуст — выполните синхронизацию с Google на дашборде.",
    }
