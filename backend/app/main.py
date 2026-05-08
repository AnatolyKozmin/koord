import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.bootstrap import (
    cleanup_generic_masters_sql,
    init_db,
    migrate_from_redis_if_empty,
    migrate_schema_add_reviewer_faculties_table,
    migrate_schema_add_user_faculty,
    seed_master_users_sql,
    seed_reviewer_users_sql,
    seed_superadmin_sql,
)
from app.routers import admin, ankety, auth, domashki, interviews, sheets, stats
from app.services.auto_sync import auto_sync_loop


log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    migrate_schema_add_user_faculty()
    migrate_schema_add_reviewer_faculties_table()
    migrate_from_redis_if_empty()
    seed_superadmin_sql()
    seed_master_users_sql()
    cleanup_generic_masters_sql()
    rv = seed_reviewer_users_sql()
    s = get_settings()
    log.info(
        "seed reviewers: created=%s skipped_existing=%s expected=%s domain=%s pwd_set=%s note=%s",
        rv.get("created"),
        rv.get("skipped_existing"),
        rv.get("total"),
        s.master_seed_domain,
        bool(s.master_seed_password),
        rv.get("note", ""),
    )

    sync_task: asyncio.Task | None = None
    if s.auto_sync_interval_sec and s.auto_sync_interval_sec > 0:
        sync_task = asyncio.create_task(auto_sync_loop(s.auto_sync_interval_sec))
    else:
        log.info("auto_sync: disabled (set AUTO_SYNC_INTERVAL_SEC=300 to enable)")

    try:
        yield
    finally:
        if sync_task is not None:
            sync_task.cancel()
            try:
                await sync_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="Koord Verification API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(ankety.router, prefix="/api")
app.include_router(domashki.router, prefix="/api")
app.include_router(interviews.router, prefix="/api")
app.include_router(sheets.router, prefix="/api")
app.include_router(stats.router, prefix="/api")


@app.get("/")
def root() -> dict:
    """Корень API: веб-интерфейс отдаётся отдельным сервисом (см. docker-compose, порт фронта)."""
    return {
        "service": "Koord Verification API",
        "health": "/health",
        "docs": "/docs",
        "api": "/api",
        "note": "Веб-интерфейс (логин и страницы) — отдельный порт, в compose обычно 8010 → не этот URL.",
    }


@app.get("/login")
def login_hint() -> dict:
    return {
        "detail": "Это адрес API. Страница входа — во фронтенде (откройте порт веб-приложения, например :8010, не :8011).",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
