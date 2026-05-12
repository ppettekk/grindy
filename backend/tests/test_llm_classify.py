"""Тесты для services.llm_classify."""
from __future__ import annotations

import asyncio

import pytest

from app.schemas import VacancyDTO
from app.services.filter import AudienceClassification, classify_audience
from app.services.llm_keys import (
    LLMKeyPool,
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
def _reset_pool():
    reset_pool_for_testing()
    yield
    reset_pool_for_testing()


def _attach_stub_pool(llm, *keys):
    pool = LLMKeyPool(entries=[KeyEntry(k) for k in keys])
    llm._pool = pool
    return pool


def _dto(title="Курьер", description="", min_age=14, company="ООО Тест"):
    return VacancyDTO(
        source="trudvsem", external_id="t-1",
        title=title, description=description, company=company,
        url="https://example.com/v/1", min_age=min_age,
    )


# ── is_ambiguous ──────────────────────────────────────────────────────────


def test_ambiguous_student_default():
    dto = _dto("Помощник", "Несложная работа в офисе", min_age=18)
    aud = classify_audience(dto)
    assert aud.audience == "student"
    amb, r = is_ambiguous(dto, aud, "Помощник и ассистент")
    assert amb and r == "student_default"


def test_ambiguous_no_category():
    dto = _dto("Странная работа", "Очень длинное описание " * 10, min_age=14)
    amb, r = is_ambiguous(dto, AudienceClassification("teen", 14, None), None)
    assert amb and r == "no_category"


def test_ambiguous_short_description():
    dto = _dto("Курьер", "Доставка", min_age=14)
    amb, r = is_ambiguous(dto, AudienceClassification("teen", 14, None), "Курьерская доставка")
    assert amb and r == "short_description"


def test_ambiguous_teen_with_experience_hint():
    desc = (
        "Подойдёт школьникам. Желательно знание базовой грамоты и умение "
        "общаться с людьми. График гибкий, обучение на месте."
    )
    dto = _dto("Курьер", desc, min_age=14)
    amb, r = is_ambiguous(dto, AudienceClassification("teen", 14, None), "Курьерская доставка")
    assert amb and r.startswith("teen_with_signal:")


def test_not_ambiguous_clear_teen():
    desc = (
        "Берём от 14 лет, обучение на месте, гибкий график. "
        "Никаких особых требований нет. Работа в районе метро."
    )
    dto = _dto("Курьер", desc, min_age=14)
    amb, _r = is_ambiguous(dto, AudienceClassification("teen", 14, None), "Курьерская доставка")
    assert amb is False


def test_not_ambiguous_clear_student():
    desc = (
        "Работа от 18 лет. Без опыта работы, обучение на месте. "
        "Гибкий график, можно совмещать с учёбой в вузе."
    )
    dto = _dto("Бариста", desc, min_age=18)
    aud = classify_audience(dto)
    assert aud.audience == "student"
    amb, _r = is_ambiguous(dto, aud, "Фастфуд и общепит")
    assert amb is False


# ── _parse ────────────────────────────────────────────────────────────────


def test_parse_clean_json():
    r = _parse('{"audience":"teen","min_age":14,"category":"Курьерская доставка","reason":"x","confidence":0.92}')
    assert r is not None
    assert r.audience == "teen" and r.min_age == 14
    assert r.category == "Курьерская доставка" and r.confidence == 0.92


def test_parse_markdown_fence():
    r = _parse('```json\n{"audience":"student","min_age":18,"category":null,"reason":"","confidence":0.5}\n```')
    assert r and r.audience == "student" and r.category is None


def test_parse_unknown_category_dropped():
    r = _parse('{"audience":"teen","min_age":14,"category":"Лесорубы","reason":"x","confidence":0.9}')
    assert r and r.category is None


def test_parse_invalid_audience_returns_none():
    assert _parse('{"audience":"alien","min_age":14,"category":null,"reason":"x","confidence":0.9}') is None


def test_parse_min_age_normalised_to_audience():
    r = _parse('{"audience":"teen","min_age":42,"category":null,"reason":"x","confidence":0.9}')
    assert r and r.min_age == 14


def test_parse_garbage_returns_none():
    assert _parse("не JSON") is None
    assert _parse("") is None


# ── LLMClassifier — успех/таймаут/ошибка/кэш/лимит ────────────────────────


@pytest.mark.asyncio
async def test_classify_success_overrides(monkeypatch):
    llm = LLMClassifier(enabled=True, max_calls=10, min_confidence=0.7, timeout_sec=2)
    _attach_stub_pool(llm, "k1")

    async def fake_generate(prompt):
        return ('{"audience":"adult_only","min_age":18,'
                '"category":"Курьерская доставка","reason":"опыт","confidence":0.95}')

    monkeypatch.setattr(llm, "_generate", fake_generate)
    res = await llm.classify(_dto())
    assert res is not None and res.audience == "adult_only"
    assert llm.calls_used == 1


@pytest.mark.asyncio
async def test_classify_low_confidence_returned(monkeypatch):
    llm = LLMClassifier(enabled=True, max_calls=10)
    _attach_stub_pool(llm, "k1")

    async def fake_generate(prompt):
        return '{"audience":"student","min_age":18,"category":null,"reason":"x","confidence":0.4}'

    monkeypatch.setattr(llm, "_generate", fake_generate)
    res = await llm.classify(_dto())
    assert res is not None and res.confidence == 0.4


@pytest.mark.asyncio
async def test_classify_error_returns_none(monkeypatch):
    llm = LLMClassifier(enabled=True, max_calls=10)
    _attach_stub_pool(llm, "k1")

    async def fake_generate(prompt):
        raise RuntimeError("API exploded")

    monkeypatch.setattr(llm, "_generate", fake_generate)
    res = await llm.classify(_dto())
    assert res is None
    assert llm.errors == 1 and llm.calls_used == 1


@pytest.mark.asyncio
async def test_classify_timeout(monkeypatch):
    llm = LLMClassifier(enabled=True, max_calls=10, timeout_sec=0.05)
    _attach_stub_pool(llm, "k1")

    async def slow_generate(prompt):
        await asyncio.sleep(0.5)
        return "{}"

    monkeypatch.setattr(llm, "_generate", slow_generate)
    res = await llm.classify(_dto())
    assert res is None and llm.errors == 1


@pytest.mark.asyncio
async def test_classify_respects_budget(monkeypatch):
    llm = LLMClassifier(enabled=True, max_calls=2)
    _attach_stub_pool(llm, "k1")
    cnt = 0

    async def fake_generate(prompt):
        nonlocal cnt; cnt += 1
        return ('{"audience":"teen","min_age":14,'
                '"category":"Курьерская доставка","reason":"x","confidence":0.9}')

    monkeypatch.setattr(llm, "_generate", fake_generate)
    await llm.classify(_dto("a", "d1"))
    await llm.classify(_dto("b", "d2"))
    res3 = await llm.classify(_dto("c", "d3"))
    assert cnt == 2 and res3 is None and llm.budget_left == 0


@pytest.mark.asyncio
async def test_classify_lru_cache(monkeypatch):
    llm = LLMClassifier(enabled=True, max_calls=10)
    _attach_stub_pool(llm, "k1")
    cnt = 0

    async def fake_generate(prompt):
        nonlocal cnt; cnt += 1
        return ('{"audience":"teen","min_age":14,'
                '"category":"Курьерская доставка","reason":"x","confidence":0.9}')

    monkeypatch.setattr(llm, "_generate", fake_generate)
    dto = _dto("Курьер", "Доставка еды по городу")
    a = await llm.classify(dto)
    b = await llm.classify(dto)
    assert a is b and cnt == 1


@pytest.mark.asyncio
async def test_classify_disabled():
    llm = LLMClassifier(enabled=False, max_calls=10)
    assert llm.available is False
    assert (await llm.classify(_dto())) is None


@pytest.mark.asyncio
async def test_classify_no_pool():
    llm = LLMClassifier(enabled=True, max_calls=10)
    llm._pool = None
    assert llm.available is False
    assert (await llm.classify(_dto())) is None


# ── Ротация ключей в _generate (мок call_provider) ────────────────────────


@pytest.mark.asyncio
async def test_generate_rotates_on_quota(monkeypatch):
    pool = LLMKeyPool(entries=[KeyEntry("k1"), KeyEntry("k2")])
    llm = LLMClassifier(enabled=True, max_calls=10)
    llm._pool = pool
    seen_keys = []

    async def fake_call_provider(prompt, *, api_key, **kw):
        seen_keys.append(api_key)
        if api_key == "k1":
            raise RuntimeError("429 quota exceeded")
        return '{"audience":"teen","min_age":14,"category":null,"reason":"ok","confidence":0.9}'

    monkeypatch.setattr("app.services.llm_classify.call_provider", fake_call_provider)
    res = await llm.classify(_dto())
    assert res is not None and res.audience == "teen"
    assert seen_keys == ["k1", "k2"]
    assert pool.entries[0].disabled is True
    assert pool.entries[1].disabled is False


@pytest.mark.asyncio
async def test_generate_no_rotation_on_transient(monkeypatch):
    pool = LLMKeyPool(entries=[KeyEntry("k1"), KeyEntry("k2")])
    llm = LLMClassifier(enabled=True, max_calls=10)
    llm._pool = pool

    async def fake_call_provider(prompt, *, api_key, **kw):
        raise RuntimeError("connection reset")

    monkeypatch.setattr("app.services.llm_classify.call_provider", fake_call_provider)
    res = await llm.classify(_dto())
    assert res is None
    assert pool.entries[0].disabled is False
    assert pool.entries[1].disabled is False
    assert llm.errors == 1


@pytest.mark.asyncio
async def test_generate_all_keys_exhausted(monkeypatch):
    pool = LLMKeyPool(entries=[KeyEntry("k1"), KeyEntry("k2")])
    llm = LLMClassifier(enabled=True, max_calls=10)
    llm._pool = pool

    async def fake_call_provider(prompt, *, api_key, **kw):
        raise RuntimeError("API key not valid")

    monkeypatch.setattr("app.services.llm_classify.call_provider", fake_call_provider)
    res = await llm.classify(_dto())
    assert res is None
    assert pool.available is False
    assert llm.errors == 1
