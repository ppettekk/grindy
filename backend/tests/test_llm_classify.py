"""Тесты для services.llm_classify."""
from __future__ import annotations

import asyncio
import sys

import pytest

from app.schemas import VacancyDTO
from app.services.filter import AudienceClassification, classify_audience
from app.services.gemini_keys import (
    GeminiKeyPool,
    KeyEntry,
    reset_pool_for_testing,
)
from app.services.llm_classify import (
    LLMClassifier,
    LLMResult,
    _parse,
    is_ambiguous,
)


@pytest.fixture(autouse=True)
def _reset_gemini_pool():
    reset_pool_for_testing()
    yield
    reset_pool_for_testing()


def _attach_stub_pool(llm: LLMClassifier, *keys: str) -> GeminiKeyPool:
    pool = GeminiKeyPool(entries=[KeyEntry(k) for k in keys])
    llm._pool = pool
    return pool


def _dto(title="Курьер", description="", min_age=14, company="ООО Тест"):
    return VacancyDTO(
        source="trudvsem",
        external_id="t-1",
        title=title,
        description=description,
        company=company,
        url="https://example.com/v/1",
        min_age=min_age,
    )


# ── is_ambiguous ──────────────────────────────────────────────────────────


def test_ambiguous_student_default():
    dto = _dto("Помощник", "Несложная работа в офисе", min_age=18)
    aud = classify_audience(dto)
    assert aud.audience == "student"
    amb, reason = is_ambiguous(dto, aud, "Помощник и ассистент")
    assert amb is True
    assert reason == "student_default"


def test_ambiguous_no_category():
    dto = _dto("Странная работа", "Очень длинное описание " * 10, min_age=14)
    aud = AudienceClassification("teen", 14, None)
    amb, reason = is_ambiguous(dto, aud, None)
    assert amb is True
    assert reason == "no_category"


def test_ambiguous_short_description():
    dto = _dto("Курьер", "Доставка", min_age=14)
    aud = AudienceClassification("teen", 14, None)
    amb, reason = is_ambiguous(dto, aud, "Курьерская доставка")
    assert amb is True
    assert reason == "short_description"


def test_ambiguous_teen_with_experience_hint():
    desc = (
        "Подойдёт школьникам. Желательно знание базовой грамоты и умение "
        "общаться с людьми. График гибкий, обучение на месте."
    )
    dto = _dto("Курьер", desc, min_age=14)
    aud = AudienceClassification("teen", 14, None)
    amb, reason = is_ambiguous(dto, aud, "Курьерская доставка")
    assert amb is True
    assert reason is not None and reason.startswith("teen_with_signal:")


def test_not_ambiguous_clear_teen():
    desc = (
        "Берём от 14 лет, обучение на месте, гибкий график. "
        "Никаких особых требований нет. Работа в районе метро."
    )
    dto = _dto("Курьер", desc, min_age=14)
    aud = AudienceClassification("teen", 14, None)
    amb, _ = is_ambiguous(dto, aud, "Курьерская доставка")
    assert amb is False


def test_not_ambiguous_clear_student():
    desc = (
        "Работа от 18 лет. Без опыта работы, обучение на месте. "
        "Гибкий график, можно совмещать с учёбой в вузе."
    )
    dto = _dto("Бариста", desc, min_age=18)
    aud = classify_audience(dto)
    assert aud.audience == "student"
    amb, _ = is_ambiguous(dto, aud, "Фастфуд и общепит")
    assert amb is False


# ── _parse ────────────────────────────────────────────────────────────────


def test_parse_clean_json():
    text = '{"audience":"teen","min_age":14,"category":"Курьерская доставка","reason":"подросткам","confidence":0.92}'
    r = _parse(text)
    assert r is not None
    assert r.audience == "teen"
    assert r.min_age == 14
    assert r.category == "Курьерская доставка"
    assert r.confidence == 0.92


def test_parse_markdown_fence():
    text = '```json\n{"audience":"student","min_age":18,"category":null,"reason":"","confidence":0.5}\n```'
    r = _parse(text)
    assert r is not None
    assert r.audience == "student"
    assert r.category is None


def test_parse_unknown_category_dropped():
    text = '{"audience":"teen","min_age":14,"category":"Лесорубы","reason":"x","confidence":0.9}'
    r = _parse(text)
    assert r is not None and r.category is None


def test_parse_invalid_audience_returns_none():
    text = '{"audience":"alien","min_age":14,"category":null,"reason":"x","confidence":0.9}'
    assert _parse(text) is None


def test_parse_min_age_normalised_to_audience():
    text = '{"audience":"teen","min_age":42,"category":null,"reason":"x","confidence":0.9}'
    r = _parse(text)
    assert r is not None and r.min_age == 14


def test_parse_garbage_returns_none():
    assert _parse("это не JSON") is None
    assert _parse("") is None


# ── LLMClassifier — успех/таймаут/ошибка/кэш/лимит ────────────────────────


@pytest.mark.asyncio
async def test_classify_success_overrides(monkeypatch):
    llm = LLMClassifier(enabled=True, max_calls=10, min_confidence=0.7, timeout_sec=2)
    _attach_stub_pool(llm, "k1")

    async def fake_generate(prompt):
        return (
            '{"audience":"adult_only","min_age":18,'
            '"category":"Курьерская доставка","reason":"опыт от 2 лет","confidence":0.95}'
        )

    monkeypatch.setattr(llm, "_generate", fake_generate)
    res = await llm.classify(_dto())
    assert res is not None
    assert res.audience == "adult_only"
    assert res.confidence == 0.95
    assert llm.calls_used == 1


@pytest.mark.asyncio
async def test_classify_low_confidence_returned_but_ignored_by_caller(monkeypatch):
    llm = LLMClassifier(enabled=True, max_calls=10, min_confidence=0.7, timeout_sec=2)
    _attach_stub_pool(llm, "k1")

    async def fake_generate(prompt):
        return '{"audience":"student","min_age":18,"category":null,"reason":"x","confidence":0.4}'

    monkeypatch.setattr(llm, "_generate", fake_generate)
    res = await llm.classify(_dto())
    assert res is not None
    assert res.confidence == 0.4


@pytest.mark.asyncio
async def test_classify_error_returns_none_and_counts(monkeypatch):
    llm = LLMClassifier(enabled=True, max_calls=10)
    _attach_stub_pool(llm, "k1")

    async def fake_generate(prompt):
        raise RuntimeError("API exploded")

    monkeypatch.setattr(llm, "_generate", fake_generate)
    res = await llm.classify(_dto())
    assert res is None
    assert llm.errors == 1
    assert llm.calls_used == 1


@pytest.mark.asyncio
async def test_classify_timeout(monkeypatch):
    llm = LLMClassifier(enabled=True, max_calls=10, timeout_sec=0.05)
    _attach_stub_pool(llm, "k1")

    async def slow_generate(prompt):
        await asyncio.sleep(0.5)
        return "{}"

    monkeypatch.setattr(llm, "_generate", slow_generate)
    res = await llm.classify(_dto())
    assert res is None
    assert llm.errors == 1


@pytest.mark.asyncio
async def test_classify_respects_budget(monkeypatch):
    llm = LLMClassifier(enabled=True, max_calls=2)
    _attach_stub_pool(llm, "k1")

    call_count = 0
    async def fake_generate(prompt):
        nonlocal call_count
        call_count += 1
        return (
            '{"audience":"teen","min_age":14,'
            '"category":"Курьерская доставка","reason":"x","confidence":0.9}'
        )

    monkeypatch.setattr(llm, "_generate", fake_generate)
    await llm.classify(_dto("Курьер 1", "desc 1"))
    await llm.classify(_dto("Курьер 2", "desc 2"))
    res3 = await llm.classify(_dto("Курьер 3", "desc 3"))
    assert call_count == 2
    assert res3 is None
    assert llm.calls_used == 2
    assert llm.budget_left == 0


@pytest.mark.asyncio
async def test_classify_lru_cache(monkeypatch):
    llm = LLMClassifier(enabled=True, max_calls=10)
    _attach_stub_pool(llm, "k1")

    call_count = 0
    async def fake_generate(prompt):
        nonlocal call_count
        call_count += 1
        return (
            '{"audience":"teen","min_age":14,'
            '"category":"Курьерская доставка","reason":"x","confidence":0.9}'
        )

    monkeypatch.setattr(llm, "_generate", fake_generate)
    dto = _dto("Курьер", "Доставка еды по городу")
    a = await llm.classify(dto)
    b = await llm.classify(dto)
    assert a is b
    assert call_count == 1
    assert llm.calls_used == 1


@pytest.mark.asyncio
async def test_classify_disabled_returns_none():
    llm = LLMClassifier(enabled=False, max_calls=10)
    assert llm.available is False
    res = await llm.classify(_dto())
    assert res is None
    assert llm.calls_used == 0


@pytest.mark.asyncio
async def test_classify_no_model_returns_none():
    llm = LLMClassifier(enabled=True, max_calls=10)
    llm._pool = None
    assert llm.available is False
    res = await llm.classify(_dto())
    assert res is None


# ── Ротация ключей в _generate ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_rotates_on_quota(monkeypatch):
    """quota-ошибка от первого ключа → переключение → второй вызов ОК."""
    pool = GeminiKeyPool(entries=[KeyEntry("k1"), KeyEntry("k2")])
    llm = LLMClassifier(enabled=True, max_calls=10)
    llm._pool = pool
    llm._configured_key = None

    call_keys: list[str] = []

    class _FakeGenAI:
        @staticmethod
        def configure(api_key):
            llm._current_test_key = api_key

        class GenerativeModel:
            def __init__(self, model_name): pass

            def generate_content(self_inner, prompt, generation_config=None):
                key = llm._current_test_key
                call_keys.append(key)
                if key == "k1":
                    raise RuntimeError("RESOURCE_EXHAUSTED: quota")
                class _Resp:
                    text = '{"audience":"teen","min_age":14,"category":null,"reason":"ok","confidence":0.9}'
                return _Resp()

    monkeypatch.setitem(sys.modules, "google.generativeai", _FakeGenAI)
    res = await llm.classify(_dto())
    assert res is not None
    assert res.audience == "teen"
    assert call_keys == ["k1", "k2"]
    assert pool.entries[0].disabled is True
    assert pool.entries[0].disabled_reason == "quota"
    assert pool.entries[1].disabled is False


@pytest.mark.asyncio
async def test_generate_no_rotation_on_transient_error(monkeypatch):
    pool = GeminiKeyPool(entries=[KeyEntry("k1"), KeyEntry("k2")])
    llm = LLMClassifier(enabled=True, max_calls=10)
    llm._pool = pool
    llm._configured_key = None

    class _FakeGenAI:
        @staticmethod
        def configure(api_key):
            llm._current_test_key = api_key

        class GenerativeModel:
            def __init__(self, model_name): pass
            def generate_content(self_inner, prompt, generation_config=None):
                raise RuntimeError("connection reset")

    monkeypatch.setitem(sys.modules, "google.generativeai", _FakeGenAI)
    res = await llm.classify(_dto())
    assert res is None
    assert pool.entries[0].disabled is False
    assert pool.entries[1].disabled is False
    assert llm.errors == 1


@pytest.mark.asyncio
async def test_generate_all_keys_exhausted_returns_none(monkeypatch):
    pool = GeminiKeyPool(entries=[KeyEntry("k1"), KeyEntry("k2")])
    llm = LLMClassifier(enabled=True, max_calls=10)
    llm._pool = pool
    llm._configured_key = None

    class _FakeGenAI:
        @staticmethod
        def configure(api_key):
            llm._current_test_key = api_key

        class GenerativeModel:
            def __init__(self, model_name): pass
            def generate_content(self_inner, prompt, generation_config=None):
                raise RuntimeError("API key not valid")

    monkeypatch.setitem(sys.modules, "google.generativeai", _FakeGenAI)
    res = await llm.classify(_dto())
    assert res is None
    assert pool.available is False
    assert llm.errors == 1
