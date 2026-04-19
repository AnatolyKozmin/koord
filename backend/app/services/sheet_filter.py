"""Фильтрация строк листа для роли user (супер-админ видит всё)."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.services.assignments_service import assignable_sheet_names, get_assignment


def filter_sheet_values(sheet_name: str, values: list[list[Any]], user: dict) -> list[list[Any]]:
    if user.get("role") == "super_admin":
        return values
    if sheet_name not in assignable_sheet_names():
        return values

    s = get_settings()
    if sheet_name == s.sheet_name_interviews:
        return _filter_interviews_columns(values, user)

    email = user.get("email", "")
    assign = get_assignment(email)
    allowed = set(assign.get(sheet_name, []))
    if not values:
        return []
    header = values[0]
    if not allowed:
        return [header]

    out: list[list[Any]] = [header]
    for i in range(1, len(values)):
        if i in allowed:
            out.append(values[i])
    return out


def _filter_interviews_columns(values: list[list[Any]], user: dict) -> list[list[Any]]:
    """
    Лист «Собеседования»: в назначениях — индексы **колонок** кандидатов.
    В выдаче остаётся колонка A (подписи строк) + назначенные столбцы.
    """
    email = user.get("email", "")
    assign = get_assignment(email)
    allowed = sorted(set(assign.get(get_settings().sheet_name_interviews, [])))
    if not values:
        return []
    if not allowed:
        return []

    keep = [0] + allowed
    out: list[list[Any]] = []
    for row in values:
        line: list[Any] = []
        for c in keep:
            line.append(row[c] if c < len(row) else "")
        out.append(line)
    return out


def filter_sheet_rows_with_indices(
    sheet_name: str,
    values: list[list[Any]],
    user: dict,
) -> tuple[list[Any] | None, list[tuple[int, list[Any]]]]:
    """
    Как filter_sheet_values, но возвращает пары (индекс строки в полном листе 0-based, ячейки строки).
    Нужно для записи баллов в A1 (номер строки в Google = index + 1).
    """
    if not values:
        return None, []
    s = get_settings()
    if sheet_name == s.sheet_name_interviews:
        filtered = filter_sheet_values(sheet_name, values, user)
        header = filtered[0] if filtered else None
        pairs = [(i, filtered[i]) for i in range(len(filtered))]
        return header, pairs

    header = values[0]
    if user.get("role") == "super_admin":
        return header, [(i, values[i]) for i in range(1, len(values))]
    if sheet_name not in assignable_sheet_names():
        return header, [(i, values[i]) for i in range(1, len(values))]

    email = user.get("email", "")
    assign = get_assignment(email)
    allowed = set(assign.get(sheet_name, []))
    if not allowed:
        return header, []

    out: list[tuple[int, list[Any]]] = []
    for i in range(1, len(values)):
        if i in allowed:
            out.append((i, values[i]))
    return header, out
