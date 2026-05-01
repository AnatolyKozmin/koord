from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(32))
    # Подпись в дашборде («Мастер 1»); если null — генерируется по порядку
    master_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Факультет (супер-админ задаёт вручную)
    faculty: Mapped[str | None] = mapped_column(String(64), nullable=True)

    assignments: Mapped[list["Assignment"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Assignment(Base):
    """Назначение строки листа (или колонки для «Собеседования») проверяющему."""

    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "sheet_name", "item_index", "axis", name="uq_user_sheet_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    sheet_name: Mapped[str] = mapped_column(String(255), index=True)
    item_index: Mapped[int] = mapped_column(Integer)
    # row — индекс строки в values[]; column — индекс колонки (лист «Собеседования»)
    axis: Mapped[str] = mapped_column(String(8), default="row")

    user: Mapped["User"] = relationship(back_populates="assignments")
