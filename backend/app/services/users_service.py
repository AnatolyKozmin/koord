"""Пользователи и роли в SQL (SQLite / PostgreSQL)."""

from __future__ import annotations

from typing import Literal

from passlib.context import CryptContext
from sqlalchemy import select

from app.db.models import User
from app.db.session import SessionLocal

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

Role = Literal["super_admin", "user"]


def _bcrypt_password(password: str) -> str:
    b = password.encode("utf-8")
    if len(b) <= 72:
        return password
    return b[:72].decode("utf-8", errors="ignore")


def hash_password(password: str) -> str:
    return pwd_context.hash(_bcrypt_password(password))


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(_bcrypt_password(password), password_hash)


def create_user(email: str, password: str, role: Role, faculty: str | None = None) -> None:
    em = email.lower()
    with SessionLocal() as session:
        if session.scalar(select(User.id).where(User.email == em)):
            raise ValueError("User exists")
        session.add(
            User(
                email=em,
                password_hash=hash_password(password),
                role=role,
                master_label=None,
                faculty=faculty,
            ),
        )
        session.commit()


def get_user(email: str) -> dict | None:
    em = email.lower()
    with SessionLocal() as session:
        u = session.scalars(select(User).where(User.email == em)).first()
        if not u:
            return None
        return {
            "email": u.email,
            "password_hash": u.password_hash,
            "role": u.role,
            "master_label": u.master_label,
            "faculty": u.faculty,
        }


def authenticate(email: str, password: str) -> dict | None:
    u = get_user(email)
    if not u:
        return None
    if not verify_password(password, u["password_hash"]):
        return None
    return {"email": email.lower(), "role": u["role"]}


def set_password(email: str, new_password: str) -> bool:
    em = email.lower()
    with SessionLocal() as session:
        u = session.scalars(select(User).where(User.email == em)).first()
        if not u:
            return False
        u.password_hash = hash_password(new_password)
        session.commit()
    return True


def set_user_faculty(email: str, faculty: str | None) -> bool:
    em = email.lower()
    with SessionLocal() as session:
        u = session.scalars(select(User).where(User.email == em)).first()
        if not u:
            return False
        u.faculty = faculty
        session.commit()
    return True


def list_users() -> list[dict]:
    with SessionLocal() as session:
        rows = session.scalars(
            select(User).order_by(User.faculty.asc().nulls_last(), User.master_label.asc(), User.email.asc()),
        ).all()
        return [
            {"email": u.email, "role": u.role, "master_label": u.master_label, "faculty": u.faculty} for u in rows
        ]

