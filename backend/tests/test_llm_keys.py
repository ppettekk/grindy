"""Тесты пула LLM-ключей и классификатора ошибок."""
from __future__ import annotations

import pytest

from app.services.llm_keys import (
    LLMKeyPool,
    KeyEntry,
    classify_error,
    reset_pool_for_testing,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_pool_for_testing()
    yield
    reset_pool_for_testing()


def _pool(*keys):
    return LLMKeyPool(entries=[KeyEntry(k) for k in keys])


def test_empty_pool_unavailable():
    p = _pool()
    assert p.available is False
    assert p.current is None
    assert p.active_count == 0


def test_single_key_returns_self():
    p = _pool("k1")
    assert p.available is True
    assert p.current == "k1"


def test_mark_failed_switches_to_next():
    p = _pool("k1", "k2", "k3")
    assert p.current == "k1"
    assert p.mark_failed("quota") is True
    assert p.current == "k2"
    assert p.mark_failed("quota") is True
    assert p.current == "k3"
    assert p.mark_failed("quota") is False
    assert p.available is False


def test_mark_failed_records_reason():
    p = _pool("k1", "k2")
    p.mark_failed("quota")
    assert p.entries[0].disabled is True
    assert p.entries[0].disabled_reason == "quota"


def test_current_skips_disabled():
    p = _pool("k1", "k2", "k3")
    p.entries[0].disabled = True
    p.entries[1].disabled = True
    assert p.current == "k3"


def test_reset_revives_keys():
    p = _pool("k1", "k2")
    p.mark_failed("quota")
    p.mark_failed("quota")
    assert p.available is False
    p.reset()
    assert p.available is True
    assert p.current == "k1"


@pytest.mark.parametrize("msg,expected", [
    ("429 Too Many Requests", "quota"),
    ("ResourceExhausted: quota exceeded", "quota"),
    ("RESOURCE_EXHAUSTED for project", "quota"),
    ("rate limit reached", "quota"),
    ("rate-limit triggered", "quota"),
    ("insufficient balance", "quota"),
    ("API key not valid", "invalid_key"),
    ("PERMISSION_DENIED: bad key", "invalid_key"),
    ("UNAUTHENTICATED", "invalid_key"),
    ("403 forbidden", "invalid_key"),
    ("API_KEY_INVALID", "invalid_key"),
    ("authentication failed", "invalid_key"),
    ("connection reset by peer", None),
    ("timeout while reading", None),
    ("500 internal server error", None),
    ("JSON decode failed", None),
])
def test_classify_error(msg, expected):
    assert classify_error(RuntimeError(msg)) == expected


def test_classify_error_uses_type_name():
    class ResourceExhausted(Exception): pass
    assert classify_error(ResourceExhausted("limit")) == "quota"
    class PermissionDenied(Exception): pass
    assert classify_error(PermissionDenied("nope")) == "invalid_key"


# ── settings.llm_keys ──────────────────────────────────────────────────────


def test_settings_csv(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("LLM_API_KEYS", "ka, kb , kc")
    monkeypatch.setenv("LLM_API_KEY", "klegacy")
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    get_settings.cache_clear()
    s = get_settings()
    assert s.llm_keys == ["ka", "kb", "kc", "klegacy"]
    get_settings.cache_clear()


def test_settings_dedups(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("LLM_API_KEYS", "k1,k2,k1")
    monkeypatch.setenv("LLM_API_KEY", "k2")
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    get_settings.cache_clear()
    assert get_settings().llm_keys == ["k1", "k2"]
    get_settings.cache_clear()


def test_settings_gemini_legacy_fallback(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_API_KEYS", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEYS", "g1,g2")
    monkeypatch.setenv("GEMINI_API_KEY", "g_legacy")
    get_settings.cache_clear()
    s = get_settings()
    assert s.llm_keys == ["g1", "g2", "g_legacy"]
    get_settings.cache_clear()


def test_settings_no_legacy_for_deepseek(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("LLM_API_KEYS", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "should_not_appear")
    get_settings.cache_clear()
    assert get_settings().llm_keys == []
    get_settings.cache_clear()


def test_effective_model_defaults(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("LLM_MODEL", "")
    for provider, expected in [
        ("deepseek", "deepseek-chat"),
        ("openai", "gpt-4o-mini"),
        ("closerouter", "anthropic/claude-haiku-4.5"),
    ]:
        monkeypatch.setenv("LLM_PROVIDER", provider)
        get_settings.cache_clear()
        assert get_settings().llm_effective_model == expected

    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    get_settings.cache_clear()
    assert get_settings().llm_effective_model == "gemini-2.5-flash"

    monkeypatch.setenv("LLM_MODEL", "custom-model-1")
    get_settings.cache_clear()
    assert get_settings().llm_effective_model == "custom-model-1"
    get_settings.cache_clear()


def test_effective_base_url_defaults(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("LLM_BASE_URL", "")
    for provider, expected in [
        ("deepseek", "https://api.deepseek.com"),
        ("openai", "https://api.openai.com/v1"),
        ("closerouter", "https://api.closerouter.dev/v1"),
    ]:
        monkeypatch.setenv("LLM_PROVIDER", provider)
        get_settings.cache_clear()
        assert get_settings().llm_effective_base_url == expected

    # Override
    monkeypatch.setenv("LLM_PROVIDER", "closerouter")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:8080/v1/")
    get_settings.cache_clear()
    assert get_settings().llm_effective_base_url == "http://localhost:8080/v1"

    # Gemini не использует REST openai-compat — пустой
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_BASE_URL", "")
    get_settings.cache_clear()
    assert get_settings().llm_effective_base_url == ""

    get_settings.cache_clear()
