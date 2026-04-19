"""Назначения строк/колонок листов проверяющим (SQL)."""

from __future__ import annotations

from sqlalchemy import delete, select

from app.config import get_settings
from app.db.models import Assignment, User
from app.db.session import SessionLocal


def assignable_sheet_names() -> frozenset[str]:
    s = get_settings()
    return frozenset(
        {
            s.sheet_name_ankety,
            s.sheet_name_domashki,
            s.sheet_name_enquiries,
            s.sheet_name_interviews,
        },
    )


def _axis_for_sheet(sheet_name: str) -> str:
    s = get_settings()
    return "column" if sheet_name == s.sheet_name_interviews else "row"


def get_assignment(email: str) -> dict[str, list[int]]:
    em = email.lower()
    with SessionLocal() as session:
        uid = session.scalar(select(User.id).where(User.email == em))
        if uid is None:
            return {}
        rows = session.execute(
            select(Assignment.sheet_name, Assignment.item_index, Assignment.axis).where(Assignment.user_id == uid),
        ).all()
        out: dict[str, list[int]] = {}
        for sheet_name, item_index, _axis in rows:
            out.setdefault(sheet_name, []).append(int(item_index))
        for k in out:
            out[k] = sorted(set(out[k]))
        return out


def set_assignment(email: str, mapping: dict[str, list[int]]) -> None:
    em = email.lower()
    with SessionLocal() as session:
        uid = session.scalar(select(User.id).where(User.email == em))
        if uid is None:
            return
        session.execute(delete(Assignment).where(Assignment.user_id == uid))
        for sheet_name, indices in mapping.items():
            axis = _axis_for_sheet(sheet_name)
            for x in sorted(set(int(i) for i in indices)):
                session.add(
                    Assignment(user_id=uid, sheet_name=sheet_name, item_index=x, axis=axis),
                )
        session.commit()


def merge_sheet_rows(email: str, sheet_name: str, row_indices: list[int]) -> None:
    cur = get_assignment(email)
    cur[sheet_name] = sorted(set(int(x) for x in row_indices))
    set_assignment(email, cur)


def list_all_assignments() -> dict[str, dict[str, list[int]]]:
    with SessionLocal() as session:
        rows = session.execute(
            select(User.email, Assignment.sheet_name, Assignment.item_index, Assignment.axis),
        ).all()
        out: dict[str, dict[str, list[int]]] = {}
        for email, sheet_name, item_index, _axis in rows:
            out.setdefault(email.lower(), {}).setdefault(sheet_name, []).append(int(item_index))
        for em in out:
            for sh in out[em]:
                out[em][sh] = sorted(set(out[em][sh]))
        return out


def distribute_sheet(
    sheet_name: str,
    per_user: int,
    user_emails: list[str],
    *,
    skip_header_row: bool = True,
    by_columns: bool = False,
) -> dict[str, list[int]]:
    from app.services import sheets_service
    from app.services.interviews_layout import sheet_max_column_index

    if sheet_name not in assignable_sheet_names():
        raise ValueError(f"Лист не участвует в назначениях: {sheet_name}")

    rows = sheets_service.read_sheet_cached(sheet_name)
    if not rows:
        raise ValueError("Нет данных в кэше — выполните синхронизацию таблицы")

    settings = get_settings()
    if by_columns:
        if sheet_name != settings.sheet_name_interviews:
            raise ValueError("Режим by_columns допустим только для листа «Собеседования»")
        fc = settings.sheet_interviews_first_candidate_col_index
        max_w = sheet_max_column_index(rows)
        data_indices = list(range(fc, max_w)) if max_w > fc else []
    else:
        start = 1 if skip_header_row and len(rows) > 0 else 0
        data_indices = list(range(start, len(rows)))

    if not user_emails:
        raise ValueError("Список пользователей пуст")

    chunks: list[list[int]] = []
    for i in range(0, len(data_indices), per_user):
        chunks.append(data_indices[i : i + per_user])

    result: dict[str, list[int]] = {e.lower(): [] for e in user_emails}
    emails_norm = [e.lower() for e in user_emails]
    for i, chunk in enumerate(chunks):
        who = emails_norm[i % len(emails_norm)]
        result[who].extend(chunk)

    for em in emails_norm:
        merge_sheet_rows(em, sheet_name, result.get(em, []))
    return result
