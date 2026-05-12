"""Конфигурация приложения через pydantic-settings."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # DB
    database_url: str = Field(
        default="sqlite+aiosqlite:///./grindy.db",
        validation_alias="DATABASE_URL",
    )

    # Telegram
    bot_token: str = Field(default="", validation_alias="BOT_TOKEN")
    webapp_url: str = Field(
        default="https://grindy.ru/app", validation_alias="WEBAPP_URL"
    )
    bot_proxy: str = Field(default="", validation_alias="BOT_PROXY")
    require_channel: str = Field(
        default="@grindywork", validation_alias="REQUIRE_CHANNEL"
    )
    admin_tg_ids_raw: str = Field(default="", validation_alias="ADMIN_TG_IDS")

    @property
    def admin_tg_ids(self) -> set[int]:
        out: set[int] = set()
        for x in self.admin_tg_ids_raw.split(","):
            x = x.strip()
            if x.isdigit():
                out.add(int(x))
        return out

    # Модерация
    report_autohide_threshold: int = Field(
        default=3, validation_alias="REPORT_AUTOHIDE_THRESHOLD"
    )

    # AI
    # Один ключ (legacy). Используется как fallback к GEMINI_API_KEYS.
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    # Несколько ключей через запятую — при квотах/блокировках идёт ротация.
    gemini_api_keys_raw: str = Field(
        default="", validation_alias="GEMINI_API_KEYS"
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash", validation_alias="GEMINI_MODEL"
    )

    @property
    def gemini_keys(self) -> list[str]:
        """Объединённый список ключей: GEMINI_API_KEYS (CSV) + GEMINI_API_KEY (legacy).

        Дубликаты и пустые значения убираются; порядок сохраняется.
        """
        out: list[str] = []
        seen: set[str] = set()
        for raw in (self.gemini_api_keys_raw or "").split(","):
            k = raw.strip()
            if k and k not in seen:
                out.append(k)
                seen.add(k)
        legacy = (self.gemini_api_key or "").strip()
        if legacy and legacy not in seen:
            out.append(legacy)
            seen.add(legacy)
        return out

    # LLM-классификатор аудитории/категории. Гоняется только на «сомнительных»
    # вакансиях, чтобы экономить API-кредиты. См. services/llm_classify.py.
    llm_enabled: bool = Field(default=True, validation_alias="LLM_ENABLED")
    # Жёсткий потолок LLM-вызовов за один прогон ingest — защита от внезапных
    # счетов при потоке новых вакансий.
    llm_max_calls_per_ingest: int = Field(
        default=30, validation_alias="LLM_MAX_CALLS_PER_INGEST"
    )
    # Минимальный confidence ответа LLM, чтобы перезаписать локальную
    # классификацию. Ниже — оставляем локальный результат.
    llm_min_confidence: float = Field(
        default=0.7, validation_alias="LLM_MIN_CONFIDENCE"
    )
    # Таймаут одного LLM-вызова в секундах.
    llm_timeout_sec: float = Field(
        default=8.0, validation_alias="LLM_TIMEOUT_SEC"
    )

    # Sources
    superjob_api_key: str = Field(default="", validation_alias="SUPERJOB_API_KEY")
    hh_user_agent: str = Field(
        default="Grindy/0.1 (contact@grindy.ru)", validation_alias="HH_USER_AGENT"
    )
    # HTTP/HTTPS/SOCKS5 прокси для запросов парсеров (HH/Rabota/Avito).
    parser_proxy: str = Field(default="", validation_alias="PARSER_PROXY")

    # Payments
    yookassa_shop_id: str = Field(default="", validation_alias="YOOKASSA_SHOP_ID")
    yookassa_secret_key: str = Field(
        default="", validation_alias="YOOKASSA_SECRET_KEY"
    )

    # Scheduler
    run_scheduler: bool = Field(default=True, validation_alias="RUN_SCHEDULER")
    parse_interval_min: int = Field(default=60, validation_alias="PARSE_INTERVAL_MIN")
    digest_morning: str = Field(default="0 9 * * *", validation_alias="DIGEST_MORNING")
    digest_evening: str = Field(default="0 19 * * *", validation_alias="DIGEST_EVENING")
    notify_interval_min: int = Field(
        default=30, validation_alias="NOTIFY_INTERVAL_MIN"
    )

    # Observability
    sentry_dsn: str = Field(default="", validation_alias="SENTRY_DSN")
    sentry_env: str = Field(default="prod", validation_alias="SENTRY_ENV")

    # CORS
    cors_origins_raw: str = Field(
        default="http://localhost:5173", validation_alias="CORS_ORIGINS"
    )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
