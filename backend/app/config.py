from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    rq_queue_name: str = Field(default="sheets", validation_alias="RQ_QUEUE_NAME")

    # SQLite: каталог ./data относительно рабочей директории (в Docker cwd=/app → /app/data). PostgreSQL: задайте URL.
    database_url: str = Field(
        default="sqlite:///./data/koord.db",
        validation_alias="DATABASE_URL",
    )

    secret_key: str = Field(default="dev-change-me", validation_alias="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60 * 24 * 7, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    google_application_credentials: str | None = Field(
        default=None,
        validation_alias="GOOGLE_APPLICATION_CREDENTIALS",
    )
    google_spreadsheet_id: str | None = Field(default=None, validation_alias="GOOGLE_SPREADSHEET_ID")

    # Имена вкладок в Google Таблице (как внизу листа в Sheets), должны совпадать с реальными.
    sheet_name_subs: str = Field(default="sub-bass", validation_alias="SHEET_NAME_SUBS")
    sheet_name_enquiries: str = Field(default="Enquiries", validation_alias="SHEET_NAME_ENQUIRIES")
    sheet_name_domashki: str = Field(default="Domashki", validation_alias="SHEET_NAME_DOMASHKI")
    sheet_name_ankety: str = Field(default="Анкеты", validation_alias="SHEET_NAME_ANKETY")
    sheet_name_interviews: str = Field(
        default="Собес",
        validation_alias="SHEET_NAME_INTERVIEWS",
    )
    # Лист «Собеседования»: колонка A–C — шаблон; первый столбец данных кандидата (0-based, D = 3).
    sheet_interviews_first_candidate_col_index: int = Field(
        default=3,
        ge=0,
        validation_alias="SHEET_INTERVIEWS_FIRST_CANDIDATE_COL_INDEX",
    )

    # Очередь записи в Sheets: пауза после каждого успешного запроса (снижение burst к квоте API).
    google_sheets_write_interval_sec: float = Field(
        default=0.6,
        validation_alias="GOOGLE_SHEETS_WRITE_INTERVAL_SEC",
    )
    # Повтор при 429 / 503 от Google.
    google_sheets_write_max_retries: int = Field(default=6, validation_alias="GOOGLE_SHEETS_WRITE_MAX_RETRIES")

    superadmin_email: str | None = Field(default=None, validation_alias="SUPERADMIN_EMAIL")
    superadmin_password: str | None = Field(default=None, validation_alias="SUPERADMIN_PASSWORD")

    # Автоматический фоновый sync листов + инкрементальное распределение анкет/домашек.
    # 0 — отключено. Иначе — интервал в секундах между прогонами (рекомендую 300 = 5 минут).
    auto_sync_interval_sec: int = Field(default=0, ge=0, validation_alias="AUTO_SYNC_INTERVAL_SEC")
    # Авто-распределение работает поверх всех проверяющих с непустым reviewer_faculties
    # (тех, у кого админ выставил допуски). Ничего не происходит, если их нет.

    # Автосоздание учёток мастеров отбора при старте (дашборд / назначения).
    master_count: int = Field(default=20, ge=0, le=500, validation_alias="MASTER_COUNT")
    master_seed_domain: str = Field(default="koord.local", validation_alias="MASTER_SEED_DOMAIN")
    master_seed_password: str = Field(
        default="changeme",
        validation_alias="MASTER_SEED_PASSWORD",
    )

    @field_validator(
        "google_spreadsheet_id",
        "sheet_name_subs",
        "sheet_name_enquiries",
        "sheet_name_domashki",
        "sheet_name_ankety",
        "sheet_name_interviews",
        mode="before",
    )
    @classmethod
    def _strip_sheet_and_id(cls, v: object) -> object:
        if v is None:
            return v
        if isinstance(v, str):
            return v.strip()
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
