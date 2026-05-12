"""Базовые smoke-тесты — гарантируют что приложение хотя бы стартует."""
from __future__ import annotations

import pytest


def test_import_app():
    from app.main import app
    assert app.title == "Grindy API"
    paths = [r.path for r in app.routes if hasattr(r, "path")]
    assert "/health" in paths
    assert "/api/vacancies" in paths
    assert "/api/users" in paths


@pytest.mark.asyncio
async def test_init_db():
    from app.db import init_db
    from app import models  # noqa: F401
    await init_db()


def test_bot_routers_registered():
    from aiogram import Dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage

    from bot.handlers import setup_handlers

    dp = Dispatcher(storage=MemoryStorage())
    setup_handlers(dp)
    names = {r.name for r in dp.sub_routers}
    assert names == {"start", "settings", "help", "search"}


def test_moderation_parser_and_thresholds():
    from app.services.moderation import SpamModerator
    from app.services.ingest import is_suspect

    spam = SpamModerator._parse('{"is_spam": true, "confidence": 0.92, "reason": "MLM"}')
    assert spam.is_spam is True
    assert spam.confidence == 0.92
    assert is_suspect(spam.confidence) is False  # >= 0.85 → already spam, не suspect

    suspect = SpamModerator._parse('{"is_spam": false, "confidence": 0.7, "reason": "?"}')
    assert is_suspect(suspect.confidence) is True

    md = SpamModerator._parse('```json\n{"is_spam":false,"confidence":0.1,"reason":"ok"}\n```')
    assert md.confidence == 0.1


def test_pagination_cursor_roundtrip():
    import uuid
    from app.api.vacancies import _decode_cursor, _encode_cursor

    iso = "2026-05-05T10:00:00+00:00"
    vid = uuid.uuid4()
    encoded = _encode_cursor(iso, vid)
    iso2, vid2 = _decode_cursor(encoded)
    assert iso2 == iso
    assert vid2 == vid


def test_telegram_initdata_invalid_signature():
    from app.services.tg_auth import verify_init_data

    # Невалидный hash → None (если BOT_TOKEN задан).
    # При пустом BOT_TOKEN возвращает данные без проверки (dev-режим).
    # Тестируем dev-кейс
    res = verify_init_data("user=%7B%22id%22%3A123%7D&hash=deadbeef")
    assert res is not None  # dev mode without BOT_TOKEN
    assert res.get("user", {}).get("id") == 123
