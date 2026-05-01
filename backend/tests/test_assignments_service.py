"""Назначения: JOIN в list_all_assignments и семантика assign_row."""

from __future__ import annotations

import os

import pytest

from app.services import assignments_service, users_service


def test_list_all_assignments_single_user_one_row() -> None:
    """Регрессия: без JOIN был декартов product — появлялись лишние email."""
    users_service.create_user("only@test.local", "password123459", "user")
    assignments_service.assign_row_to_user("ЛистОтбора", 10, "only@test.local")
    all_assign = assignments_service.list_all_assignments()
    assert set(all_assign.keys()) == {"only@test.local"}
    assert all_assign["only@test.local"]["ЛистОтбора"] == [10]


def test_assign_row_exclusive_per_slot() -> None:
    """Строку нельзя оставить у двух: второй координатор забирает слот."""
    users_service.create_user("u1@test.local", "pwd111111118", "user")
    users_service.create_user("u2@test.local", "pwd222222228", "user")
    sn = os.environ["SHEET_NAME_ANKETY"]

    assignments_service.assign_row_to_user(sn, 3, "u1@test.local")
    m1 = assignments_service.get_assignment("u1@test.local")
    assert sn in m1 and 3 in m1[sn]

    assignments_service.assign_row_to_user(sn, 3, "u2@test.local")
    m1b = assignments_service.get_assignment("u1@test.local")
    m2b = assignments_service.get_assignment("u2@test.local")
    assert 3 not in m1b.get(sn, [])
    assert 3 in m2b.get(sn, [])


def test_distribute_anketa_by_reviewer_faculty_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Строка идёт только к проверяющему, у которого в допусках есть канонический факультет кандидата."""
    sn = os.environ["SHEET_NAME_ANKETY"]

    headers = ["a", "b", "c", "d", "e", "f", "g", "Укажи свой факультет"]

    def _row(fac_cell: str) -> list[str]:
        r = [""] * len(headers)
        r[len(headers) - 1] = fac_cell
        return r

    fake_sheet = [
        headers,
        _row("ФЭБ"),
        _row("НАБ"),
    ]

    monkeypatch.setattr(
        "app.services.sheets_service.read_sheet_cached",
        lambda sheet: fake_sheet if sheet == sn else [],
    )

    users_service.create_user("a@test.local", "pwdaaaaaaaaa1", "user")
    users_service.create_user("b@test.local", "pwdbbbbbbbbb1", "user")
    users_service.set_user_reviewer_faculties("a@test.local", ["ФЭБ"])
    users_service.set_user_reviewer_faculties("b@test.local", ["НАБ"])

    out = assignments_service.distribute_anketa_balanced_by_faculty(
        sn,
        ["a@test.local", "b@test.local"],
    )
    assert isinstance(out["assigned"], dict)
    assert out["assigned"]["a@test.local"] == [1]
    assert out["assigned"]["b@test.local"] == [2]


def test_distribute_anketa_unknown_faculty_unassigned(monkeypatch: pytest.MonkeyPatch) -> None:
    """Нераспознанный факультет — в unassigned; при пустых допусках никому не достаётся."""
    sn = os.environ["SHEET_NAME_ANKETY"]

    headers = ["Укажи свой факультет"]

    monkeypatch.setattr(
        "app.services.sheets_service.read_sheet_cached",
        lambda sheet: [headers, ["Медицина"]] if sheet == sn else [],
    )

    users_service.create_user("a@test.local", "pwdaaaaaaaaa2", "user")
    users_service.set_user_reviewer_faculties("a@test.local", ["НАБ"])

    out = assignments_service.distribute_anketa_balanced_by_faculty(sn, ["a@test.local"])
    assert out["assigned"]["a@test.local"] == []
    assert out["unassigned"] == [1]
