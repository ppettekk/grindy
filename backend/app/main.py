from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import admin, employers, users, vacancies
from .config import settings
from .db import init_db
from .scheduler.tasks import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("grindy.api")


# Sentry init - опциональный, включается если SENTRY_DSN задан.
if settings.sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.asyncio import AsyncioIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.sentry_env,
            traces_sample_rate=0.1,
            send_default_pii=False,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                AsyncioIntegration(),
            ],
        )
        logger.info("Sentry initialised (env=%s)", settings.sentry_env)
    except ImportError:
        logger.warning("SENTRY_DSN задан, но sentry-sdk не установлен")
    except Exception as e:  # noqa: BLE001
        logger.warning("Sentry init failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    if settings.run_scheduler:
        start_scheduler()
    try:
        yield
    finally:
        if settings.run_scheduler:
            stop_scheduler()


app = FastAPI(
    title="Grindy API",
    description="Агрегатор подработки для подростков",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vacancies.router)
app.include_router(users.router)
app.include_router(employers.router)
app.include_router(admin.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
