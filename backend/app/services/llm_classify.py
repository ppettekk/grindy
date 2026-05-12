"""LLM-классификатор аудитории/категории.

Провайдер задаётся через ``LLM_PROVIDER`` (deepseek/openai/gemini), модель
через ``LLM_MODEL`` (или дефолт по провайдеру). См. services/llm_keys.py.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Literal

from ..config import settings
from ..schemas import VacancyDTO
from .categorize import CATEGORY_KEYWORDS
from .filter import AudienceClassification
from .llm_keys import call_provider, classify_error, get_pool

logger = logging.getLogger(__name__)


Audience = Literal["teen", "student", "adult_only"]


@dataclass(frozen=True)
class LLMResult:
    audience: Audience
    min_age: int
    category: str | None
    reason: str
    confidence: float


# ── is_ambiguous ──────────────────────────────────────────────────────────


_FALLBACK_CATEGORIES: frozenset[str] = frozenset({
    "Помощник и ассистент",
    "Стажировки",
})
_EXPERIENCE_HINT_TOKENS: tuple[str, ...] = (
    "опыт",
    "стаж",
    "experience",
    "знание ",
    "умение ",
    "владен",
)


def is_ambiguous(
    dto: VacancyDTO,
    audience: AudienceClassification,
    category: str | None,
) -> tuple[bool, str | None]:
    text = " ".join(filter(None, [dto.title or "", dto.description or ""])).strip()
    if (
        audience.audience == "student"
        and audience.hidden_reason is None
        and "18" not in text
        and "школьник" not in text.lower()
        and "подростк" not in text.lower()
        and "kids" not in text.lower()
    ):
        return True, "student_default"
    if category is None:
        return True, "no_category"
    if category in _FALLBACK_CATEGORIES:
        return True, f"fallback_category:{category}"
    if len((dto.description or "").strip()) < 100:
        return True, "short_description"
    if audience.audience == "teen":
        lower = text.lower()
        for tok in _EXPERIENCE_HINT_TOKENS:
            if tok in lower:
                return True, f"teen_with_signal:{tok.strip()}"
    return False, None


# ── Промт ─────────────────────────────────────────────────────────────────


_CATEGORY_LIST = sorted(CATEGORY_KEYWORDS.keys())


def _build_prompt(dto: VacancyDTO) -> str:
    cats_str = "\n".join(f"- {c}" for c in _CATEGORY_LIST)
    return f"""\
Ты классифицируешь вакансию для сервиса подработки. Определи:
1. audience — одно из:
   * "teen" — школьникам 14-18 (физический труд без опыта, простая подработка).
   * "student" — студентам и взрослым 18+ (совершеннолетие, но без многолетнего опыта).
   * "adult_only" — взрослым 20+ (опыт >=1 года, гражданство РФ, высшее образование).
2. min_age — конкретный минимум 14 / 16 / 18.
3. category — одна из списка или null:
{cats_str}
4. reason — короткое объяснение по-русски (1 предложение).
5. confidence — уверенность 0..1.

Вакансия:
Название: {dto.title or "—"}
Компания: {dto.company or "—"}
Описание: {(dto.description or "—")[:2000]}

Ответь СТРОГО одним JSON-объектом без markdown:
{{"audience": "teen|student|adult_only", "min_age": 14|16|18, "category": "..." or null, "reason": "...", "confidence": 0..1}}
"""


def _hash_dto(dto: VacancyDTO) -> str:
    payload = "|".join([dto.title or "", (dto.description or "")[:500]])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_MISS = object()


class LLMClassifier:
    """Классификатор с лимитом вызовов, кэшем и ротацией ключей."""

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        max_calls: int | None = None,
        min_confidence: float | None = None,
        timeout_sec: float | None = None,
    ) -> None:
        self.enabled = settings.llm_enabled if enabled is None else enabled
        self.max_calls = (
            settings.llm_max_calls_per_ingest if max_calls is None else max_calls
        )
        self.min_confidence = (
            settings.llm_min_confidence if min_confidence is None else min_confidence
        )
        self.timeout_sec = (
            settings.llm_timeout_sec if timeout_sec is None else timeout_sec
        )

        self.calls_used: int = 0
        self.errors: int = 0
        self._cache: OrderedDict[str, "LLMResult | None"] = OrderedDict()
        self._cache_max = 256

        self._pool = get_pool() if self.enabled else None

    @property
    def available(self) -> bool:
        return self.enabled and self._pool is not None and self._pool.available

    @property
    def budget_left(self) -> int:
        return max(0, self.max_calls - self.calls_used)

    def _cache_get(self, key: str):
        if key not in self._cache:
            return _MISS
        self._cache.move_to_end(key)
        return self._cache[key]

    def _cache_put(self, key: str, value) -> None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        if len(self._cache) > self._cache_max:
            self._cache.popitem(last=False)

    async def classify(self, dto: VacancyDTO):
        if not self.available:
            return None
        key = _hash_dto(dto)
        cached = self._cache_get(key)
        if cached is not _MISS:
            return cached
        if self.calls_used >= self.max_calls:
            logger.info("LLM budget exhausted (%d) — skipping", self.max_calls)
            return None

        prompt = _build_prompt(dto)
        self.calls_used += 1
        started = time.perf_counter()
        try:
            text = await asyncio.wait_for(
                self._generate(prompt), timeout=self.timeout_sec
            )
        except TimeoutError:
            self.errors += 1
            logger.warning(
                "LLM timeout (%.1fs) — ext=%s", self.timeout_sec, dto.external_id
            )
            self._cache_put(key, None)
            return None
        except Exception as e:  # noqa: BLE001
            self.errors += 1
            logger.warning("LLM call failed: %s — ext=%s", e, dto.external_id)
            self._cache_put(key, None)
            return None

        elapsed = time.perf_counter() - started
        result = _parse(text)
        logger.info(
            "LLM %s %.2fs ext=%s → audience=%s min_age=%s cat=%r conf=%.2f",
            settings.llm_provider,
            elapsed,
            dto.external_id,
            result.audience if result else "—",
            result.min_age if result else "—",
            result.category if result else "—",
            result.confidence if result else 0.0,
        )
        self._cache_put(key, result)
        return result

    async def _generate(self, prompt: str) -> str:
        """Запрос к LLM с авторотацией ключей при quota/invalid_key."""
        if not self._pool or not self._pool.available:
            raise RuntimeError("no active LLM keys")

        last_err: BaseException | None = None
        for _ in range(self._pool.total_count):
            key = self._pool.current
            if key is None:
                break
            try:
                return await call_provider(prompt, api_key=key)
            except Exception as e:  # noqa: BLE001
                last_err = e
                kind = classify_error(e)
                if kind is None:
                    raise  # транзиент — не виноват ключ
                if not self._pool.mark_failed(kind):
                    raise

        raise last_err or RuntimeError("all LLM keys exhausted")


# ── Парсинг ответа ───────────────────────────────────────────────────────


_VALID_AUDIENCES: frozenset[str] = frozenset({"teen", "student", "adult_only"})
_VALID_MIN_AGES: frozenset[int] = frozenset({14, 16, 18})


def _parse(text: str):
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    # raw_decode парсит первый JSON-объект и игнорирует мусор после него
    # (часто LLM приклеивают второй объект или комментарий).
    try:
        data, _end = json.JSONDecoder().raw_decode(text)
    except json.JSONDecodeError as e:
        logger.warning("LLM bad JSON: %s — %r", e, text[:200])
        return None

    audience = str(data.get("audience") or "").strip()
    if audience not in _VALID_AUDIENCES:
        logger.warning("LLM bad audience: %r", audience)
        return None

    try:
        min_age = int(data.get("min_age", 0))
    except (TypeError, ValueError):
        min_age = 0
    if min_age not in _VALID_MIN_AGES:
        min_age = 14 if audience == "teen" else 18

    category = data.get("category")
    if category in (None, "", "null"):
        category = None
    elif isinstance(category, str):
        category = category.strip() or None
    else:
        category = None
    if category and category not in _CATEGORY_LIST:
        logger.info("LLM unknown category %r — dropped", category)
        category = None

    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    reason = str(data.get("reason") or "")[:500]

    return LLMResult(
        audience=audience,  # type: ignore[arg-type]
        min_age=min_age,
        category=category,
        reason=reason,
        confidence=confidence,
    )
