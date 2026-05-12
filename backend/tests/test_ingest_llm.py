"""Интеграция LLM в ingest — без реальной БД.

Тесты проверяют поведение run_ingest с подменёнными парсерами / LLM /
модерацией / сессией. Запоминаем все вакансии, переданные в session.add,
и проверяем их атрибуты на соответствие ожидаемой логике.

Инварианты:
1. LLM с confidence ≥ min_confidence → перезаписывает audience/min_age/
   category, ставит llm_classified=True.
2. LLM с confidence < min_confidence → результат игнорируется.
3. LLM-ошибка (classify вернул None) не валит ingest, llm_errors учитывается.
4. LLM с available=False вообще не вызывается.
"""
from __future__ import annotations

import sys

import pytest

from app.schemas import VacancyDTO
from app.services.llm_classify import LLMResult

# В проде backend крутится на Python 3.11 (см. Dockerfile). Здесь же,
# в локальной sandbox-среде на 3.10, enum.StrEnum недоступен и
# app.models не импортируется. Тесты валидны только на 3.11+.
pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="enum.StrEnum requires Python 3.11+ (prod backend image uses 3.11)",
)


def _ambiguous_dto() -> VacancyDTO:
    """DTO без явных триггеров → student-дефолт → is_ambiguous == True."""
    return VacancyDTO(
        source="trudvsem",
        external_id="amb-1",
        title="Помощник в офис",
        description="Несложная работа в офисе",
        company="ООО Тест",
        url="https://example.com/v/amb-1",
        min_age=18,
    )


class _StubParser:
    """Минимальный парсер: возвращает заранее заданный список DTO."""

    source = "trudvsem"

    def __init__(self, dtos: list[VacancyDTO]):
        self._dtos = dtos

    async def fetch(self, *, limit: int = 50) -> list[VacancyDTO]:
        return self._dtos[:limit]

    async def aclose(self) -> None:
        pass


class _StubSession:
    """In-memory сессия: сохраняет всё, что .add(), и игнорирует commit."""

    def __init__(self):
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        pass

    async def execute(self, *args, **kwargs):
        # _exists всегда возвращает «не существует» → пишем все DTO.
        class _Result:
            def scalar_one_or_none(self):
                return None
        return _Result()


class _OkModerator:
    async def check(self, *a, **kw):
        from app.services.moderation import ModerationResult
        return ModerationResult(False, 0.0, "")


def _stub_vacancy_factory():
    """Подменяем models.Vacancy на простой контейнер атрибутов, чтобы не
    тащить SQLAlchemy/enum.StrEnum в sandbox-python 3.10."""

    class _StubVacancy:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class _StubEnum:
        def __init__(self, v): self.value = v
        def __repr__(self): return f"<E:{self.value}>"

    return _StubVacancy, _StubEnum


def _patch_ingest(monkeypatch, *, parsers, llm):
    """Общая часть: подменяем парсеры, LLM, модерацию, модель Vacancy и enum'ы."""
    from app.services import ingest as ingest_module

    monkeypatch.setattr(ingest_module, "ALL_PARSERS", [lambda: p for p in parsers])
    monkeypatch.setattr(ingest_module, "moderator", _OkModerator())
    monkeypatch.setattr(ingest_module, "LLMClassifier", lambda: llm)

    StubVacancy, StubEnum = _stub_vacancy_factory()
    monkeypatch.setattr(ingest_module, "Vacancy", StubVacancy)
    monkeypatch.setattr(ingest_module, "VacancySource", lambda v: StubEnum(v))
    monkeypatch.setattr(ingest_module, "VacancyFormat", lambda v: StubEnum(v))

    return ingest_module


@pytest.mark.asyncio
async def test_llm_high_confidence_overrides(monkeypatch):
    class _HighConfLLM:
        available = True
        budget_left = 30
        calls_used = 0
        errors = 0
        min_confidence = 0.7

        async def classify(self, dto):
            self.calls_used += 1
            return LLMResult(
                audience="adult_only",
                min_age=18,
                category="Помощник и ассистент",
                reason="нужен опыт работы с документами",
                confidence=0.92,
            )

    llm = _HighConfLLM()
    parser = _StubParser([_ambiguous_dto()])
    ingest = _patch_ingest(monkeypatch, parsers=[parser], llm=llm)
    sess = _StubSession()

    stats = await ingest.run_ingest(sess)

    assert len(sess.added) == 1
    v = sess.added[0]
    assert v.is_hidden is True              # adult_only → скрыта
    assert v.min_age == 18
    assert v.llm_classified is True
    assert v.hidden_reason.startswith("llm:")
    assert stats["trudvsem"]["llm_overrides"] == 1
    assert stats["trudvsem"]["llm_calls"] == 1
    assert stats["trudvsem"]["adult_only"] == 1


@pytest.mark.asyncio
async def test_llm_low_confidence_keeps_local(monkeypatch):
    class _LowConfLLM:
        available = True
        budget_left = 30
        calls_used = 0
        errors = 0
        min_confidence = 0.7

        async def classify(self, dto):
            self.calls_used += 1
            return LLMResult(
                audience="teen",
                min_age=14,
                category="Курьерская доставка",
                reason="хз",
                confidence=0.4,  # ниже порога — игнорируется
            )

    llm = _LowConfLLM()
    parser = _StubParser([_ambiguous_dto()])
    ingest = _patch_ingest(monkeypatch, parsers=[parser], llm=llm)
    sess = _StubSession()

    stats = await ingest.run_ingest(sess)

    v = sess.added[0]
    # Локальная классификация: student → min_age=18.
    assert v.min_age == 18
    assert v.llm_classified is False
    assert stats["trudvsem"]["llm_calls"] == 1
    assert stats["trudvsem"]["llm_overrides"] == 0


@pytest.mark.asyncio
async def test_llm_returning_none_does_not_break(monkeypatch):
    """classify вернул None (таймаут/ошибка). Ingest продолжает, llm_errors+1."""

    class _ErrorLLM:
        available = True
        budget_left = 30
        calls_used = 0
        errors = 0
        min_confidence = 0.7

        async def classify(self, dto):
            self.calls_used += 1
            self.errors += 1
            return None

    llm = _ErrorLLM()
    parser = _StubParser([_ambiguous_dto()])
    ingest = _patch_ingest(monkeypatch, parsers=[parser], llm=llm)
    sess = _StubSession()

    stats = await ingest.run_ingest(sess)

    assert len(sess.added) == 1
    assert sess.added[0].llm_classified is False
    assert stats["trudvsem"]["llm_errors"] == 1


@pytest.mark.asyncio
async def test_llm_unavailable_skipped(monkeypatch):
    class _DisabledLLM:
        available = False
        budget_left = 0
        calls_used = 0
        errors = 0
        min_confidence = 0.7

        async def classify(self, dto):
            raise AssertionError("classify must not be called when unavailable")

    llm = _DisabledLLM()
    parser = _StubParser([_ambiguous_dto()])
    ingest = _patch_ingest(monkeypatch, parsers=[parser], llm=llm)
    sess = _StubSession()

    stats = await ingest.run_ingest(sess)

    assert len(sess.added) == 1
    assert sess.added[0].llm_classified is False
    assert stats["trudvsem"]["llm_calls"] == 0


@pytest.mark.asyncio
async def test_llm_budget_zero_skipped(monkeypatch):
    """budget_left == 0 — classify не зовётся, локальная классификация."""

    class _BudgetExhausted:
        available = True
        budget_left = 0
        calls_used = 5
        errors = 0
        min_confidence = 0.7

        async def classify(self, dto):
            raise AssertionError("classify must not be called when budget=0")

    llm = _BudgetExhausted()
    parser = _StubParser([_ambiguous_dto()])
    ingest = _patch_ingest(monkeypatch, parsers=[parser], llm=llm)
    sess = _StubSession()

    stats = await ingest.run_ingest(sess)

    assert stats["trudvsem"]["llm_calls"] == 0
    assert sess.added[0].llm_classified is False
