import pytest

from app.constants.faculties import REVIEWER_FACULTIES
from app.schemas.admin import UserFacultyPatch


def test_reviewer_faculties_contains_expected() -> None:
    assert "НАБ" in REVIEWER_FACULTIES
    assert "СНиМК" in REVIEWER_FACULTIES


def test_user_faculty_patch_valid() -> None:
    assert UserFacultyPatch(faculty="ВШУ").faculty == "ВШУ"
    assert UserFacultyPatch(faculty=None).faculty is None


def test_user_faculty_patch_invalid() -> None:
    with pytest.raises(ValueError):
        UserFacultyPatch(faculty="Медфак")
