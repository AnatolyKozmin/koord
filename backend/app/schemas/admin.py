import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from app.constants.faculties import REVIEWER_FACULTIES

# Принимаем любой email вида user@domain.tld, включая .local и другие внутренние домены
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$|^[^@\s]+@[^@\s]+$")


def _norm_email(v: str) -> str:
    v = v.strip().lower()
    if not v or "@" not in v:
        raise ValueError("Некорректный email")
    return v


AnyEmail = Annotated[str, Field(min_length=3)]


class UserCreateRequest(BaseModel):
    email: AnyEmail
    password: str = Field(min_length=4)
    role: Literal["user", "super_admin"] = "user"
    faculty: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return _norm_email(v)

    @field_validator("faculty", mode="before")
    @classmethod
    def check_faculty_create(cls, v: object) -> str | None:
        if v is None or v == "":
            return None
        s = str(v).strip()
        if s not in REVIEWER_FACULTIES:
            raise ValueError(f"Неизвестный факультет: {s}")
        return s


class UserOutAdmin(BaseModel):
    email: str
    role: str
    master_label: str | None = None
    faculty: str | None = None
    reviewer_faculties: list[str] = Field(default_factory=list)


class AssignmentPutRequest(BaseModel):
    """Индексы строк 0-based (как в массиве values). Обычно включают строки данных; строка 0 — заголовок."""

    rows_by_sheet: dict[str, list[int]]


class DistributeRequest(BaseModel):
    sheet_name: str = Field(description="Анкеты | Домашки | Enquiries | Собеседования")
    per_user: int = Field(ge=1, le=5000)
    user_emails: list[AnyEmail]
    by_columns: bool = Field(
        default=False,
        description="Для листа «Собеседования»: распределять колонки кандидатов (D…), а не строки.",
    )

    @field_validator("user_emails", mode="before")
    @classmethod
    def normalise_emails(cls, v: list) -> list:
        return [_norm_email(str(e)) for e in v]


class SetPasswordRequest(BaseModel):
    password: str = Field(min_length=4)


class UserFacultyPatch(BaseModel):
    faculty: str | None = None

    @field_validator("faculty", mode="before")
    @classmethod
    def check_faculty_patch(cls, v: object) -> str | None:
        if v is None or v == "":
            return None
        s = str(v).strip()
        if s not in REVIEWER_FACULTIES:
            raise ValueError(f"Неизвестный факультет: {s}")
        return s


class ReviewerFacultiesPatch(BaseModel):
    """Факультеты кандидатов, которые координатор может проверять (пустой список — никакие)."""

    faculties: list[str] = Field(default_factory=list)

    @field_validator("faculties", mode="before")
    @classmethod
    def check_list(cls, v: object) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("Ожидается массив строк")
        out: list[str] = []
        for item in v:
            s = str(item).strip()
            if not s:
                continue
            if s not in REVIEWER_FACULTIES:
                raise ValueError(f"Неизвестный факультет: {s}")
            if s not in out:
                out.append(s)
        return sorted(out)


class DistributeCustomRequest(BaseModel):
    sheet_name: str = Field(description="Анкеты | Домашки | Enquiries | Собеседования")
    user_counts: dict[str, int] = Field(
        description="Словарь {email: количество_строк} для каждого проверяющего.",
    )
    by_columns: bool = Field(default=False)


class DistributeBalancedRequest(BaseModel):
    sheet_name: str = Field(description="Только лист «Анкеты»")
    user_emails: list[AnyEmail]

    @field_validator("user_emails", mode="before")
    @classmethod
    def normalise_emails(cls, v: list) -> list:
        return [_norm_email(str(e)) for e in v]


class AssignRowRequest(BaseModel):
    sheet_name: str
    row_index: int
    email: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, v: str | None) -> str | None:
        if not v:
            return None
        return _norm_email(v)
