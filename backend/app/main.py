from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.bootstrap import init_db, migrate_from_redis_if_empty, seed_master_users_sql, seed_superadmin_sql
from app.routers import admin, ankety, auth, domashki, interviews, sheets, stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    migrate_from_redis_if_empty()
    seed_superadmin_sql()
    seed_master_users_sql()
    yield


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


@app.get("/health")
def health():
    return {"status": "ok"}
