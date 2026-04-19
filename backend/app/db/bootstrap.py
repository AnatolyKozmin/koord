"""Создание таблиц и однократный перенос users / assignments из Redis."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from app.config import get_settings
from app.db.models import Assignment, Base, User
from app.db.session import SessionLocal, engine
from app.redis_client import get_redis
from app.services.users_service import hash_password


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def migrate_from_redis_if_empty() -> dict[str, Any]:
    """Если таблицы пусты, копируем данные из Redis (предыдущие версии приложения)."""
    out: dict[str, Any] = {"users_migrated": 0, "assignments_migrated": 0}
    with SessionLocal() as session:
        if session.scalar(select(User.id).limit(1)) is not None:
            return {**out, "skipped": "users already in sql"}

        r = get_redis()
        settings = get_settings()
        interviews_name = settings.sheet_name_interviews

        for key in r.scan_iter("user:*"):
            raw = r.get(key)
            if not raw:
                continue
            email = key.split(":", 1)[1]
            data = json.loads(raw)
            session.add(
                User(
                    email=email.lower(),
                    password_hash=data["password_hash"],
                    role=data.get("role", "user"),
                    master_label=None,
                ),
            )
            out["users_migrated"] += 1

        session.commit()

        # assignments после пользователей
        with SessionLocal() as s2:
            users_by_email = {u.email: u.id for u in s2.scalars(select(User)).all()}
        for key in r.scan_iter("assignments:*"):
            raw = r.get(key)
            if not raw:
                continue
            email = key.split(":", 1)[1].lower()
            uid = users_by_email.get(email)
            if uid is None:
                continue
            data = json.loads(raw)
            for sheet_name, indices in data.items():
                axis = "column" if sheet_name == interviews_name else "row"
                for idx in indices:
                    session.add(
                        Assignment(
                            user_id=uid,
                            sheet_name=sheet_name,
                            item_index=int(idx),
                            axis=axis,
                        ),
                    )
                    out["assignments_migrated"] += 1

        session.commit()

    return out


def seed_superadmin_sql() -> bool:
    settings = get_settings()
    if not settings.superadmin_email or not settings.superadmin_password:
        return False
    from app.services.users_service import create_user, get_user

    if get_user(settings.superadmin_email):
        return False
    create_user(settings.superadmin_email, settings.superadmin_password, "super_admin")
    return True


def seed_master_users_sql() -> dict[str, Any]:
    """
    Создаёт master01@…masterN@ в домене master_seed_domain с ролью user и подписью «Мастер отбора k».
    Идемпотентно: существующие email не трогаем.
    """
    settings = get_settings()
    out: dict[str, Any] = {"created": 0, "skipped_existing": 0}
    if settings.master_count <= 0:
        return {**out, "note": "MASTER_COUNT=0 — сид мастеров отключён"}
    domain = (settings.master_seed_domain or "koord.local").strip().lower() or "koord.local"
    pwd = settings.master_seed_password
    if not pwd:
        return {**out, "note": "MASTER_SEED_PASSWORD пуст — сид мастеров пропущен"}

    with SessionLocal() as session:
        for k in range(1, settings.master_count + 1):
            email = f"master{k:02d}@{domain}"
            if session.scalar(select(User.id).where(User.email == email)):
                out["skipped_existing"] += 1
                continue
            session.add(
                User(
                    email=email,
                    password_hash=hash_password(pwd),
                    role="user",
                    master_label=f"Мастер отбора {k}",
                ),
            )
            out["created"] += 1
        session.commit()
    return out
