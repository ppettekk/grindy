"""AI-модерация спама/MLM через Google Gemini.

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
from .gemini_keys import classify_error, get_pool

logger = logging.getLogger(__name__)


PROMPT = """\
Ты модератор сайта подработки для подростков 14–18 лет. Проверь вакансию и определи, является ли она реферальной схемой, сетевым маркетингом (MLM), мошеннической или иначе непригодной для подростков.

Признаки спама / MLM / мошенничества:
- Упоминание партнёрской программы, реферальной ссылки, приглашения друзей
- Курьер/доставка с подозрительно высокой оплатой и без чёткого работодателя
- "Заработай приглашая друзей", "удалённая работа без опыта 2000+ ₽/час"
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
    """Тонкая обёртка над google-generativeai с graceful-fallback."""

    def __init__(self) -> None:
        # Используем общий пул ключей — moderation и LLM-классификатор шарят
        # один и тот же пул. Если ключ умрёт в одном — второй сразу узнает.
        self._pool = get_pool()
        self._configured_key: str | None = None
        self._model = None
        if not self._pool.available:
            logger.info("Gemini key pool empty — spam moderation disabled")

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
            text = await self._generate(prompt)
        except Exception as e:  # noqa: BLE001
            logger.warning("Gemini call failed: %s", e)
            return ModerationResult(False, 0.0, f"error: {e}")

        return self._parse(text)

    async def _generate(self, prompt: str) -> str:
        """Вызов Gemini с авторотацией ключей при quota/invalid_key."""
        import google.generativeai as genai

        last_err: BaseException | None = None
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
                    raise
                if not self._pool.mark_failed(kind):
                    raise

        raise last_err or RuntimeError("all Gemini keys exhausted")

    @staticmethod
    def _parse(text: str) -> ModerationResult:
        text = text.strip()
        # Срезаем возможные ```json блоки.
        if text.startswith("```"):
            text = text.strip("`")
            text = text.removeprefix("json").strip()
        try:
            data = json.loads(text)
            return ModerationResult(
                is_spam=bool(data.get("is_spam")),
                confidence=float(data.get("confidence", 0.0)),
                reason=str(data.get("reason", ""))[:500],
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Bad moderator JSON: %s — %r", e, text[:200])
            return ModerationResult(False, 0.0, f"parse error: {e}")


moderator = SpamModerator()
