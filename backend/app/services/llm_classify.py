"""LLM-классификатор аудитории/категории через Google Gemini.

Логика:
* Гоняется только на «сомнительных» вакансиях (см. ``is_ambiguous``).
* Возвращает ``LLMResult`` или ``None``, если LLM выключен/упал/таймаут.
* In-memory LRU-кэш по hash(title|description), чтобы не дёргать API на
  дубли в рамках одного прогона.
* Жёсткий лимит вызовов задаётся вызывающим кодом (см. ``LLMClassifier.budget``).

Промт жёстко форсирует структуру ответа: одна JSON-строка с полями
``audience``, ``min_age``, ``category``, ``reason``, ``confidence``.
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
from .gemini_keys import classify_error, get_pool

logger = logging.getLogger(__name__)


Audience = Literal["teen", "student", "adult_only"]


@dataclass(frozen=True)
class LLMResult:
    audience: Audience
    min_age: int                       # 14 / 16 / 18
    category: str | None               # один из CATEGORY_KEYWORDS.keys() или None
    reason: str                        # объяснение для логов / аналитики
    confidence: float                  # 0..1


# ── is_ambiguous ──────────────────────────────────────────────────────────


# Категории-«мусорная корзина», на которых стоит уточнить через LLM.
# Это очень общие категории, в которые часто попадает что попало.
_FALLBACK_CATEGORIES: frozenset[str] = frozenset({
    "Помощник и ассистент",
    "Стажировки",
})

# Слова, потенциально намекающие на опыт работы, которые наши regex'ы могут
# не поймать (нестандартные формулировки в description).
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
    """Решает, стоит ли догонять вакансию LLM-классификатором.

    Возвращает (is_ambiguous, причина). Причина нужна только для логов
    и тестов — основной потребитель смотрит на bool.
    """
    text = " ".join(filter(None, [dto.title or "", dto.description or ""])).strip()

    # 1) Дефолт student без всяких триггеров (классификатор «угадывал»).
    if (
        audience.audience == "student"
        and audience.hidden_reason is None
        # Простая эвристика: нет «18», нет accept_kids, нет «школьник» в тексте —
        # классификатор просто упал в дефолт.
        and "18" not in text
        and "школьник" not in text.lower()
        and "подростк" not in text.lower()
        and "kids" not in text.lower()
    ):
        return True, "student_default"

    # 2) Категория — мусорная корзина или вообще не определилась.
    if category is None:
        return True, "no_category"
    if category in _FALLBACK_CATEGORIES:
        return True, f"fallback_category:{category}"

    # 3) Слишком короткое описание (regex'ам неоткуда брать сигналы).
    if len((dto.description or "").strip()) < 100:
        return True, "short_description"

    # 4) Сказали teen, но в тексте есть намёки на опыт — LLM перепроверит.
    if audience.audience == "teen":
        lower = text.lower()
        for tok in _EXPERIENCE_HINT_TOKENS:
            if tok in lower:
                return True, f"teen_with_signal:{tok.strip()}"

    return False, None


# ── LLM-вызов ─────────────────────────────────────────────────────────────


_CATEGORY_LIST = sorted(CATEGORY_KEYWORDS.keys())


def _build_prompt(dto: VacancyDTO) -> str:
    """Жёстко-структурированный промт для Gemini."""
    cats_str = "\n".join(f"- {c}" for c in _CATEGORY_LIST)
    return f"""\
Ты классифицируешь вакансию для сервиса подработки. Определи:
1. audience — для кого подходит вакансия (одно из):
   * "teen" — школьникам 14–18 (физический труд без опыта, простая подработка).
   * "student" — студентам и взрослым 18+ (требует совершеннолетия, но без многолетнего опыта).
   * "adult_only" — взрослым 20+ (требует опыт ≥1 года, гражданство РФ, высшее образование).
2. min_age — конкретный минимальный возраст 14 / 16 / 18.
3. category — одна из категорий ниже (выбери максимально близкую) или null, если ни одна не подходит:
{cats_str}
4. reason — короткое объяснение по-русски (1 предложение).
5. confidence — уверенность ответа 0..1.

Вакансия:
Название: {dto.title or "—"}
Компания: {dto.company or "—"}
Описание: {(dto.description or "—")[:2000]}

Ответь СТРОГО одним JSON-объектом без markdown, без пояснений вокруг:
{{"audience": "teen|student|adult_only", "min_age": 14|16|18, "category": "..." or null, "reason": "...", "confidence": 0..1}}
"""


def _hash_dto(dto: VacancyDTO) -> str:
    """Стабильный hash для LRU-кэша. Не зависит от external_id."""
    payload = "|".join([dto.title or "", (dto.description or "")[:500]])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class LLMClassifier:
    """LLM-классификатор с лимитом вызовов и кэшем.

    Создавайте **один на ingest-цикл** — счётчик ``calls_used`` локален.
    """

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
        self._cache: OrderedDict[str, LLMResult | None] = OrderedDict()
        self._cache_max = 256

        # Лениво конфигурируем genai под текущий ключ из пула. Сохраняем
        # последний использованный ключ, чтобы не reconfigure'ить впустую.
        self._pool = get_pool() if self.enabled else None
        self._configured_key: str | None = None
        self._model = None

        if self.enabled and self._pool and self._pool.available:
            try:
                import google.generativeai as genai  # noqa: F401
            except Exception as e:  # noqa: BLE001
                logger.exception("google-generativeai import failed: %s", e)
                self._pool = None
        elif self.enabled:
            logger.info("LLM classifier: нет активных Gemini-ключей — выключен")

    @property
    def available(self) -> bool:
        return self.enabled and self._pool is not None and self._pool.available

    @property
    def budget_left(self) -> int:
        return max(0, self.max_calls - self.calls_used)

    def _cache_get(self, key: str) -> LLMResult | None | object:
        """Возвращает sentinel _MISS, если в кэше нет (чтобы не путать с None)."""
        if key not in self._cache:
            return _MISS
        # LRU — двигаем ключ в конец.
        self._cache.move_to_end(key)
        return self._cache[key]

    def _cache_put(self, key: str, value: LLMResult | None) -> None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        if len(self._cache) > self._cache_max:
            self._cache.popitem(last=False)

    async def classify(self, dto: VacancyDTO) -> LLMResult | None:
        """Возвращает результат LLM или None при ошибке/выключенном/превышенном лимите."""
        if not self.available:
            return None

        key = _hash_dto(dto)
        cached = self._cache_get(key)
        if cached is not _MISS:
            return cached  # может быть и None — это валидный негативный кэш

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
            logger.warning("LLM timeout (%.1fs) — ext=%s", self.timeout_sec, dto.external_id)
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
            "LLM %.2fs ext=%s → audience=%s min_age=%s cat=%r conf=%.2f",
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
        """Запрос к Gemini с авторотацией ключей при quota/invalid_key.

        Перебираем все живые ключи пула в одном вызове. Каждая транзиентная
        ошибка (таймаут, сеть, парс) пробрасывается выше — она не повод
        менять ключ. quota/invalid_key — повод; помечаем текущий мёртвым
        и пробуем следующий.
        """
        if not self._pool or not self._pool.available:
            raise RuntimeError("no active Gemini keys")

        import google.generativeai as genai

        last_err: BaseException | None = None
        # Жёсткий потолок попыток — равен числу ключей. Защита от бесконечного
        # цикла, если что-то пойдёт криво в логике.
        for _ in range(self._pool.total_count):
            key = self._pool.current
            if key is None:
                break
            if key != self._configured_key:
                genai.configure(api_key=key)
                self._model = genai.GenerativeModel(settings.gemini_model)
                self._configured_key = key

            def _sync() -> str:
                resp = self._model.generate_content(  # type: ignore[union-attr]
                    prompt,
                    generation_config={
                        "temperature": 0.0,
                        "response_mime_type": "application/json",
                    },
                )
                return resp.text or ""

            try:
                return await asyncio.to_thread(_sync)
            except Exception as e:  # noqa: BLE001
                last_err = e
                kind = classify_error(e)
                if kind is None:
                    raise  # транзиентная ошибка — наверх, ключ не виноват
                # quota / invalid_key — помечаем и пробуем следующий
                if not self._pool.mark_failed(kind):
                    raise

        # Если вышли из цикла без return — все ключи дохлые.
        raise last_err or RuntimeError("all Gemini keys exhausted")


# Sentinel для cache hit vs miss.
_MISS = object()


# ── Парсинг ответа LLM ────────────────────────────────────────────────────


_VALID_AUDIENCES: frozenset[str] = frozenset({"teen", "student", "adult_only"})
_VALID_MIN_AGES: frozenset[int] = frozenset({14, 16, 18})


def _parse(text: str) -> LLMResult | None:
    """Парсит JSON-ответ Gemini. Возвращает None при невалидной структуре."""
    text = (text or "").strip()
    if not text:
        return None
    # Срезаем возможные ```json блоки.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
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
        # Жёстко не падаем — нормализуем к значению по audience.
        min_age = 14 if audience == "teen" else 18

    category = data.get("category")
    if category in (None, "", "null"):
        category = None
    elif isinstance(category, str):
        category = category.strip() or None
    else:
        category = None
    # Валидируем категорию — она должна быть из нашего справочника.
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
