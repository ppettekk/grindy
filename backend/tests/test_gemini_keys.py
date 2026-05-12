"""Тесты пула Gemini-ключей и классификатора ошибок."""
from __future__ import annotations

import pytest

from app.services.gemini_keys import (
    GeminiKeyPool,
    KeyEntry,
    classify_error,
    reset_pool_for_testing,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_pool_for_testing()
    yield
    reset_pool_for_testing()


def _pool(*keys: str) -> GeminiKeyPool:
    return GeminiKeyPool(entries=[KeyEntry(k) for k in keys])


# ── GeminiKeyPool: базовое поведение ──────────────────────────────────────


def test_empty_pool_unavailable():
    p = _pool()
    assert p.available is False
    assert p.current is None
    assert p.active_count == 0


def test_single_key_returns_self():
    p = _pool("k1")
    assert p.available is True
    assert p.current == "k1"
    assert p.active_count == 1


def test_mark_failed_switches_to_next():
    p = _pool("k1", "k2", "k3")
    assert p.current == "k1"

    assert p.mark_failed("quota") is True       # ещё 2 живых
    assert p.current == "k2"
    assert p.active_count == 2

    assert p.mark_failed("quota") is True       # 1 живой
    assert p.current == "k3"
    assert p.active_count == 1

    assert p.mark_failed("quota") is False      # все мертвы
    assert p.current is None
    assert p.available is False


def test_mark_failed_records_reason():
    p = _pool("k1", "k2")
    p.mark_failed("quota")
    assert p.entries[0].disabled is True
    assert p.entries[0].disabled_reason == "quota"
    assert p.entries[0].failures == 1


def test_current_skips_disabled():
    p = _pool("k1", "k2", "k3")
    p.entries[0].disabled = True
    p.entries[1].disabled = True
    # idx=0, но первый и второй disabled — должен прыгнуть на третий.
    assert p.current == "k3"


def test_reset_revives_keys():
    p = _pool("k1", "k2")
    p.mark_failed("quota")
    p.mark_failed("quota")
    assert p.available is False
    p.reset()
    assert p.available is True
    assert p.active_count == 2
    assert p.current == "k1"


# ── classify_error ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "msg,expected",
    [
        ("429 Too Many Requests", "quota"),
        ("ResourceExhausted: quota exceeded", "quota"),
        ("RESOURCE_EXHAUSTED for project", "quota"),
        ("rate limit reached", "quota"),
        ("rate-limit triggered", "quota"),
        ("API key not valid", "invalid_key"),
        ("PERMISSION_DENIED: bad key", "invalid_key"),
        ("UNAUTHENTICATED", "invalid_key"),
        ("403 forbidden", "invalid_key"),
        ("API_KEY_INVALID", "invalid_key"),
        # Транзиентные — не меняем ключ
        ("connection reset by peer", None),
        ("timeout while reading", None),
        ("500 internal server error", None),
        ("JSON decode failed", None),
    ],
)
def test_classify_error(msg, expected):
    err = RuntimeError(msg)
    assert classify_error(err) == expected


def test_classify_error_uses_type_name():
    """Тип исключения тоже учитывается — google-api-core кидает свои классы."""
    class ResourceExhausted(Exception):
        pass
    assert classify_error(ResourceExhausted("limit hit")) == "quota"

    class PermissionDenied(Exception):
        pass
    assert classify_error(PermissionDenied("nope")) == "invalid_key"


# ── Интеграция с settings ──────────────────────────────────────────────────


def test_from_settings_picks_up_csv(monkeypatch):
    from app.config import settings, get_settings
    monkeypatch.setenv("GEMINI_API_KEYS", "key_a, key_b , key_c")
    monkeypatch.setenv("GEMINI_API_KEY", "key_legacy")
    get_settings.cache_clear()
    fresh = get_settings()
    keys = fresh.gemini_keys
    assert keys == ["key_a", "key_b", "key_c", "key_legacy"]
    get_settings.cache_clear()  # restore for other tests


def test_from_settings_dedups(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("GEMINI_API_KEYS", "k1,k2,k1")
    monkeypatch.setenv("GEMINI_API_KEY", "k2")  # дубль с CSV
    get_settings.cache_clear()
    fresh = get_settings()
    assert fresh.gemini_keys == ["k1", "k2"]
    get_settings.cache_clear()


def test_from_settings_empty(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("GEMINI_API_KEYS", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()
    fresh = get_settings()
    assert fresh.gemini_keys == []
    get_settings.cache_clear()
