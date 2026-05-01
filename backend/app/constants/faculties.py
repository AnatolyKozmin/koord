"""Факультеты для разметки проверяющих (координаторов)."""

from app.constants.ankety import _norm

REVIEWER_FACULTIES: tuple[str, ...] = (
    "НАБ",
    "ВШУ",
    "ФЭБ",
    "ИТиАБД",
    "Финфак",
    "Юрфак",
    "МЭО",
    "СНиМК",
)


def canonical_reviewer_faculty(cell: object) -> str | None:
    """Сопоставить значение ячейки «Укажи свой факультет» со списком REVIEWER_FACULTIES (регистр/пробелы игнорируются)."""
    if cell is None:
        return None
    v = _norm(str(cell))
    if not v:
        return None
    for f in REVIEWER_FACULTIES:
        if _norm(f) == v:
            return f
    return None
