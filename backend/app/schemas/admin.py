from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=4)
    role: Literal["user", "super_admin"] = "user"


class UserOutAdmin(BaseModel):
    email: str
    role: str


class AssignmentPutRequest(BaseModel):
    """Индексы строк 0-based (как в массиве values). Обычно включают строки данных; строка 0 — заголовок."""

    rows_by_sheet: dict[str, list[int]]


class DistributeRequest(BaseModel):
    sheet_name: str = Field(description="Анкеты | Домашки | Enquiries | Собеседования")
    per_user: int = Field(ge=1, le=5000)
    user_emails: list[EmailStr]
    by_columns: bool = Field(
        default=False,
        description="Для листа «Собеседования»: распределять колонки кандидатов (D…), а не строки.",
    )
