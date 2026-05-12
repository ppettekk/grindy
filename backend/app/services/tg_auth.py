"""Валидация Telegram WebApp initData по подписи бота.

См. https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import parse_qsl

from ..config import settings


def parse_init_data(init_data: str) -> dict:
    return dict(parse_qsl(init_data, strict_parsing=False))


def verify_init_data(init_data: str, *, max_age_seconds: int = 86400) -> dict | None:
    """Возвращает распарсенный user dict, либо None если подпись невалидна.

    Если BOT_TOKEN не настроен — возвращает данные без проверки (dev-режим).
    """
    if not init_data:
        return None

    parsed = parse_init_data(init_data)
    received_hash = parsed.pop("hash", None)

    if not settings.bot_token:
        # dev-режим: возвращаем как есть
        return _extract_user(parsed)

    if not received_hash:
        return None

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items()) if k != "hash"
    )
    secret_key = hmac.new(
        b"WebAppData", settings.bot_token.encode(), hashlib.sha256
    ).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, received_hash):
        return None

    return _extract_user(parsed)


def _extract_user(parsed: dict) -> dict:
    user_raw = parsed.get("user")
    if not user_raw:
        return {"raw": parsed}
    try:
        user = json.loads(user_raw)
    except Exception:  # noqa: BLE001
        user = {}
    return {"user": user, "raw": parsed}
