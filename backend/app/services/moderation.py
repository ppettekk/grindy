"""AI-модерация спама/MLM через LLM-провайдер (DeepSeek/OpenAI/Gemini).

Возвращает {"is_spam": bool, "confidence": float 0..1, "reason": str}.

Пороги (из ТЗ §5):
  confidence >= 0.85 → is_spam=True (вакансия скрывается)
  0.6 <= c < 0.85    → suspect (показывается с пометкой)
  c < 0.6            → ok
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

from ..config import settings
from .llm_keys import call_provider, classify_error, get_pool

logger = logging.getLogger(__name__)


PROMPT = """\
Ты модератор сайта подработки для подростков 14-18 лет. Проверь вакансию и определи, является ли она реферальной схемой, сетевым маркетингом (MLM), мошеннической или иначе непригодной для подростков.

Признаки спама / MLM / мошенничества:
- Упоминание партнёрской программы, реферальной ссылки, приглашения друзей
- Реферальная схема подключения к сервисам доставки: "подключим к Яндекс
  Еде / Самокату / Деливери", "курьер-партнёр", "бонус за регистрацию",
  "выплата за подключение друга" — это посредник-вербовщик, НЕ работодатель
- Курьер/доставка с подозрительно высокой оплатой и без чёткого работодателя
- "Заработай приглашая друзей", "удалённая работа без опыта 2000+ руб/час"
- Требование вложений или покупки стартового набора
- Размытое описание без конкретного работодателя
- Нелегальная или взрослая работа

Вакансия:
Название: {title}
Компания: {company}
Описание: {description}

Ответь строго JSON-объектом без markdown-разметки:
{{"is_spam": true|false, "confidence": число 0..1, "reason": "короткое объяснение по-русски"}}
"""


@dataclass
class ModerationResult:
    is_spam: bool
    confidence: float
    reason: str

    @property
    def is_suspect(self) -> bool:
        return 0.6 <= self.confidence < 0.85


class SpamModerator:
    """Модерация через общий пул LLM-ключей (provider из settings.llm_provider)."""

    def __init__(self) -> None:
        self._pool = get_pool()
        if not self._pool.available:
            logger.info("LLM key pool empty — spam moderation disabled")

    @property
    def available(self) -> bool:
        return self._pool is not None and self._pool.available

    async def check(
        self,
        title: str,
        company: str | None,
        description: str | None,
    ) -> ModerationResult:
        if not self.available:
            return ModerationResult(False, 0.0, "moderation disabled")

        prompt = PROMPT.format(
            title=title or "—",
            company=company or "—",
            description=(description or "—")[:1500],
        )
        try:
            text = await asyncio.wait_for(
                self._generate(prompt), timeout=settings.llm_timeout_sec
            )
        except TimeoutError:
            logger.warning("LLM moderator timeout")
            return ModerationResult(False, 0.0, "timeout")
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM moderator failed: %s", e)
            return ModerationResult(False, 0.0, f"error: {e}")

        return self._parse(text)

    async def _generate(self, prompt: str) -> str:
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
                    raise
                if not self._pool.mark_failed(kind):
                    raise

        raise last_err or RuntimeError("all LLM keys exhausted")

    @staticmethod
    def _parse(text: str) -> ModerationResult:
        text = (text or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        try:
            # raw_decode — игнорируем мусор после первого JSON-объекта.
            data, _ = json.JSONDecoder().raw_decode(text)
            return ModerationResult(
                is_spam=bool(data.get("is_spam")),
                confidence=float(data.get("confidence", 0.0)),
                reason=str(data.get("reason", ""))[:500],
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Bad moderator JSON: %s — %r", e, text[:200])
            return ModerationResult(False, 0.0, f"parse error: {e}")


moderator = SpamModerator()
