"""Назначения: JOIN в list_all_assignments и семантика assign_row."""

from __future__ import annotations

import os

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
