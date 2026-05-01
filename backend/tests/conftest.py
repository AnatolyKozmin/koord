"""Conftest выполняется до остальных тестов."""

from __future__ import annotations

import os
import tempfile

import pytest
from sqlalchemy import text

_db = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_db.name}"

os.environ.setdefault("SECRET_KEY", "pytest-secret-min-16-chars-xxxx")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/15")

os.environ["MASTER_COUNT"] = "0"
os.environ["MASTER_SEED_PASSWORD"] = ""

for _k in ("SUPERADMIN_EMAIL", "SUPERADMIN_PASSWORD"):
    os.environ.pop(_k, None)

os.environ.setdefault("SHEET_NAME_ANKETY", "ТестАнкеты")
os.environ.setdefault("SHEET_NAME_DOMASHKI", "ТестДомашки")

import app.main as main_app

from fastapi.testclient import TestClient

from app.db import bootstrap
from app.db.session import SessionLocal

# После этого импорт — engine уже указывает на тестовую БД из DATABASE_URL выше.


@pytest.fixture(autouse=True)
def stub_redis_migrate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_app, "migrate_from_redis_if_empty", lambda: {"skipped": "test"})


@pytest.fixture(autouse=True)
def clean_db() -> None:
    bootstrap.init_db()
    bootstrap.migrate_schema_add_user_faculty()
    with SessionLocal() as session:
        session.execute(text("DELETE FROM assignments"))
        session.execute(text("DELETE FROM users"))
        session.commit()
    yield


@pytest.fixture
def client() -> TestClient:
    with TestClient(main_app.app) as c:
        yield c


@pytest.fixture
def admin_headers() -> dict[str, str]:
    from app.auth.jwt import create_access_token

    from app.services import users_service

    users_service.create_user("adm@test.local", "PWD123458888", "super_admin")
    t = create_access_token("adm@test.local", "super_admin")
    return {"Authorization": f"Bearer {t}"}
