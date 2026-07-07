"""Конфигурация приложения через pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

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
    # Юзернейм бота без @. Используется для deep-link на WebApp в уведомлениях.
    bot_username: str = Field(
        default="grindyworkbot", validation_alias="BOT_USERNAME"
    )
    # Short name WebApp, заданный через @BotFather (/setdomain / /newapp).
    # Финальная ссылка: t.me/<bot_username>/<webapp_short_name>?startapp=...
    webapp_short_name: str = Field(
        default="app", validation_alias="WEBAPP_SHORT_NAME"
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

    # ── LLM provider ──────────────────────────────────────────────────
    llm_provider: Literal["deepseek", "openai", "gemini", "closerouter"] = Field(
        default="deepseek", validation_alias="LLM_PROVIDER"
    )
    llm_api_key: str = Field(default="", validation_alias="LLM_API_KEY")
    llm_api_keys_raw: str = Field(default="", validation_alias="LLM_API_KEYS")
    llm_model: str = Field(default="", validation_alias="LLM_MODEL")
    llm_base_url: str = Field(default="", validation_alias="LLM_BASE_URL")

    llm_enabled: bool = Field(default=True, validation_alias="LLM_ENABLED")
    llm_max_calls_per_ingest: int = Field(
        default=30, validation_alias="LLM_MAX_CALLS_PER_INGEST"
    )
    llm_min_confidence: float = Field(
        default=0.7, validation_alias="LLM_MIN_CONFIDENCE"
    )
    llm_timeout_sec: float = Field(
        default=8.0, validation_alias="LLM_TIMEOUT_SEC"
    )

    # Legacy Gemini
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    gemini_api_keys_raw: str = Field(
        default="", validation_alias="GEMINI_API_KEYS"
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash", validation_alias="GEMINI_MODEL"
    )

    @property
    def llm_keys(self) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()

        def _add_csv(raw: str) -> None:
            for k in (raw or "").split(","):
                k = k.strip()
                if k and k not in seen:
                    out.append(k); seen.add(k)

        def _add_one(k: str) -> None:
            k = (k or "").strip()
            if k and k not in seen:
                out.append(k); seen.add(k)

        _add_csv(self.llm_api_keys_raw)
        _add_one(self.llm_api_key)
        if self.llm_provider == "gemini":
            _add_csv(self.gemini_api_keys_raw)
            _add_one(self.gemini_api_key)
        return out

    @property
    def llm_effective_model(self) -> str:
        if self.llm_model.strip():
            return self.llm_model.strip()
        return {
            "deepseek": "deepseek-chat",
            "openai": "gpt-4o-mini",
            "gemini": self.gemini_model or "gemini-2.5-flash",
            "closerouter": "anthropic/claude-haiku-4.5",
        }.get(self.llm_provider, "deepseek-chat")

    @property
    def llm_effective_base_url(self) -> str:
        if self.llm_base_url.strip():
            return self.llm_base_url.strip().rstrip("/")
        return {
            "deepseek": "https://api.deepseek.com",
            "openai": "https://api.openai.com/v1",
            "closerouter": "https://api.closerouter.dev/v1",
        }.get(self.llm_provider, "")

    # Sources
    superjob_api_key: str = Field(default="", validation_alias="SUPERJOB_API_KEY")
    hh_user_agent: str = Field(
        default="Grindy/0.1 (contact@grindy.ru)", validation_alias="HH_USER_AGENT"
    )
    parser_proxy: str = Field(default="", validation_alias="PARSER_PROXY")

    # Avito (отдельный воркер на Playwright — см. app/avito_worker.py)
    avito_enabled: bool = Field(default=True, validation_alias="AVITO_ENABLED")
    # Как часто avito-worker парсит Avito (минуты). Avito тяжёлый — реже.
    avito_interval_min: int = Field(
        default=120, validation_alias="AVITO_INTERVAL_MIN"
    )
    # Отдельный прокси для Avito: ОБЯЗАТЕЛЬНО статичный/sticky IP.
    # Ротационный (PARSER_PROXY) рвёт браузерные сессии посреди навигации.
    # Если пусто — fallback на PARSER_PROXY (но Avito с ротацией не работает).
    avito_proxy: str = Field(default="", validation_alias="AVITO_PROXY")

    @property
    def avito_effective_proxy(self) -> str:
        return (self.avito_proxy or self.parser_proxy or "").strip()

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
