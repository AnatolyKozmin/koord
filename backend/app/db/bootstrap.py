"""Создание таблиц и однократный перенос users / assignments из Redis."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import inspect, select, text

from app.config import get_settings
from app.db.models import Assignment, Base, User
from app.db.session import SessionLocal, engine
from app.redis_client import get_redis
from app.services.users_service import hash_password


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def migrate_schema_add_user_faculty() -> None:
    """Для существующих БД: добавить колонку users.faculty (SQLite / PostgreSQL)."""
    try:
        insp = inspect(engine)
        cols = [c["name"] for c in insp.get_columns("users")]
    except Exception:
        return
    if "faculty" in cols:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN faculty VARCHAR(64)"))


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
                    faculty=None,
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


def migrate_schema_add_reviewer_faculties_table() -> None:
    """Для существующих БД: создать таблицу user_reviewer_faculties если её нет."""
    try:
        insp = inspect(engine)
        if "user_reviewer_faculties" not in insp.get_table_names():
            with engine.begin() as conn:
                conn.execute(text(
                    "CREATE TABLE user_reviewer_faculties ("
                    "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,"
                    "  faculty VARCHAR(64) NOT NULL,"
                    "  UNIQUE (user_id, faculty)"
                    ")"
                ))
    except Exception:
        pass


def seed_superadmin_sql() -> bool:
    settings = get_settings()
    if not settings.superadmin_email or not settings.superadmin_password:
        return False
    from app.services.users_service import create_user, get_user

    if get_user(settings.superadmin_email):
        return False
    create_user(settings.superadmin_email, settings.superadmin_password, "super_admin")
    return True


_REVIEWER_LIST: list[tuple[str, str]] = [
    ("basova.e", "Басова Екатерина"),
    ("bedretdinova.al", "Бедретдинова Алина"),
    ("bedretdinova.s", "Бедретдинова Софья"),
    ("velichko.o", "Величко Олег"),
    ("deriglazova.d", "Дериглазова Дарья"),
    ("dzyarskaya.p", "Дзярская Полина"),
    ("iskenderov.a", "Искендеров Амиль"),
    ("kalmykova.p", "Калмыкова Полина"),
    ("kirilyuk.i", "Кирилюк Илья"),
    ("kitaeva.a", "Китаева Амуланга"),
    ("kovalev.g", "Ковалев Георгий"),
    ("koptelova.e", "Коптелова Ева"),
    ("kushnir.e", "Кушнир Елизавета"),
    ("larina.yu", "Ларина Юлия"),
    ("levina.a", "Левина Алиса"),
    ("margaryan.m", "Маргарян Марианна"),
    ("mitrofanova.p", "Митрофанова Полина"),
    ("pavlova.d", "Павлова Дарья"),
    ("paliy.v", "Палий Валерия"),
    ("pivovarova.a", "Пивоварова Анастасия"),
    ("pogrebnyak.v", "Погребняк Вероника"),
    ("sagatova.d", "Сагатова Дана"),
    ("sysoeva.k", "Сысоева Кира"),
    ("shityagina.a", "Шитягина Арина"),
    ("shishkova.al", "Шишкова Алина"),
    ("shonya.a", "Шоня Анастасия"),
]


def seed_reviewer_users_sql() -> dict[str, Any]:
    """
    Создаёт учётные записи для 26 проверяющих.
    Email строится как <slug>@<domain>.  Идемпотентно.
    """
    settings = get_settings()
    domain = (settings.master_seed_domain or "koord.local").strip().lower() or "koord.local"
    pwd = settings.master_seed_password
    out: dict[str, Any] = {"created": 0, "skipped_existing": 0, "total": len(_REVIEWER_LIST)}
    if not pwd:
        return {**out, "note": "MASTER_SEED_PASSWORD пуст — сид проверяющих пропущен"}
    with SessionLocal() as session:
        for slug, full_name in _REVIEWER_LIST:
            email = f"{slug}@{domain}"
            if session.scalar(select(User.id).where(User.email == email)):
                out["skipped_existing"] += 1
                continue
            session.add(
                User(
                    email=email,
                    password_hash=hash_password(pwd),
                    role="user",
                    master_label=full_name,
                    faculty=None,
                ),
            )
            out["created"] += 1
        session.commit()
    return out


def cleanup_generic_masters_sql() -> dict[str, Any]:
    """
    Удаляет технических пользователей вида masterNN@<domain>, созданных seed_master_users_sql.
    Вызывается при MASTER_COUNT=0, чтобы убрать ранее сгенерированные аккаунты.
    """
    import re

    settings = get_settings()
    domain = (settings.master_seed_domain or "koord.local").strip().lower() or "koord.local"
    pattern = re.compile(rf"^master\d+@{re.escape(domain)}$")
    deleted = 0
    with SessionLocal() as session:
        users = session.scalars(select(User).where(User.role == "user")).all()
        for u in users:
            if pattern.match(u.email):
                session.delete(u)
                deleted += 1
        session.commit()
    return {"deleted_generic_masters": deleted}


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
                    faculty=None,
                ),
            )
            out["created"] += 1
        session.commit()
    return out
