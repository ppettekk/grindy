"""Пул API-ключей и низкоуровневый вызов LLM-провайдера.

Поддерживает: DeepSeek (default), OpenAI, Gemini.
DeepSeek и OpenAI — через REST HTTP (httpx); Gemini — через REST HTTP тоже,
чтобы не тащить google-generativeai SDK.

Пул шарится между LLM-классификатором и SpamModerator (синглтон процесса).
"""
from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Literal

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


ErrorKind = Literal["quota", "invalid_key"]


@dataclass
class KeyEntry:
    key: str
    disabled: bool = False
    disabled_reason: str | None = None
    failures: int = 0


@dataclass
class LLMKeyPool:
    """Round-robin пул ключей с маркировкой нерабочих."""

    entries: list[KeyEntry] = field(default_factory=list)
    idx: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def from_settings(cls) -> "LLMKeyPool":
        return cls(entries=[KeyEntry(k) for k in settings.llm_keys])

    @property
    def available(self) -> bool:
        return any(not e.disabled for e in self.entries)

    @property
    def active_count(self) -> int:
        return sum(1 for e in self.entries if not e.disabled)

    @property
    def total_count(self) -> int:
        return len(self.entries)

    @property
    def current(self) -> str | None:
        with self._lock:
            if not self.entries:
                return None
            for _ in range(len(self.entries)):
                e = self.entries[self.idx]
                if not e.disabled:
                    return e.key
                self.idx = (self.idx + 1) % len(self.entries)
            return None

    def mark_failed(self, reason) -> bool:
        with self._lock:
            if not self.entries:
                return False
            cur = self.entries[self.idx]
            cur.disabled = True
            cur.disabled_reason = str(reason)
            cur.failures += 1
            logger.warning(
                "LLM key %s disabled (%s); active=%d/%d",
                _mask(cur.key),
                reason,
                sum(1 for e in self.entries if not e.disabled),
                len(self.entries),
            )
            self.idx = (self.idx + 1) % len(self.entries)
        return self.available

    def reset(self) -> None:
        with self._lock:
            for e in self.entries:
                e.disabled = False
                e.disabled_reason = None
            self.idx = 0


def _mask(key: str) -> str:
    if not key:
        return "***"
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


# ── Классификация ошибок (общая для всех провайдеров) ────────────────────


_RATE_LIMIT_PATTERNS = re.compile(
    r"(?:resource[\s_-]?exhausted|429|quota|rate[\s_-]?limit|too\s+many\s+requests"
    r"|insufficient[\s_-]?balance)",
    re.IGNORECASE,
)
_KEY_INVALID_PATTERNS = re.compile(
    r"(?:permission[\s_-]?denied|unauthenticated|invalid[\s_-]?api[\s_-]?key"
    r"|api\s+key\s+not\s+valid|api[\s_-]?key[\s_-]?invalid|401|403"
    r"|authentication[\s_-]?fail)",
    re.IGNORECASE,
)


def classify_error(err: BaseException):
    """quota / invalid_key / None. None = транзиент, ключ менять не надо."""
    msg = f"{type(err).__name__}: {err}"
    if _KEY_INVALID_PATTERNS.search(msg):
        return "invalid_key"
    if _RATE_LIMIT_PATTERNS.search(msg):
        return "quota"
    return None


# ── Process-level singleton ──────────────────────────────────────────────


_pool: "LLMKeyPool | None" = None
_pool_lock = threading.Lock()


def get_pool() -> LLMKeyPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = LLMKeyPool.from_settings()
                logger.info(
                    "LLM key pool initialised: provider=%s, model=%s, keys=%d",
                    settings.llm_provider,
                    settings.llm_effective_model,
                    _pool.total_count,
                )
    return _pool


def reset_pool_for_testing() -> None:
    """Сброс синглтона. Используется только тестами."""
    global _pool
    _pool = None


# ── Transport: REST-вызовы провайдеров ───────────────────────────────────


class LLMHTTPError(RuntimeError):
    """Превращаем неуспешный HTTP-ответ в исключение со statusом в тексте,
    чтобы classify_error мог его правильно классифицировать (401/403/429)."""

    def __init__(self, status: int, body: str):
        super().__init__(f"{status}: {body[:300]}")
        self.status = status
        self.body = body


async def call_provider(
    prompt: str,
    *,
    provider: str | None = None,
    api_key: str,
    model: str | None = None,
    timeout: float | None = None,
    json_mode: bool = True,
) -> str:
    """Универсальный вызов: возвращает текст ответа (assistant content / candidate).

    Транспорт под капотом подбирается по provider:
      * deepseek / openai / closerouter → OpenAI-compatible /chat/completions
      * gemini                          → generativelanguage REST
    """
    provider = provider or settings.llm_provider
    model = model or settings.llm_effective_model
    timeout = timeout if timeout is not None else settings.llm_timeout_sec

    if provider in ("deepseek", "openai", "closerouter"):
        base = settings.llm_effective_base_url
        if not base:
            raise ValueError(
                f"LLM_BASE_URL пуст для провайдера {provider!r}; задайте через env"
            )
        return await _call_openai_compat(
            prompt,
            base_url=base,
            api_key=api_key,
            model=model,
            timeout=timeout,
            json_mode=json_mode,
        )
    if provider == "gemini":
        return await _call_gemini(
            prompt,
            api_key=api_key,
            model=model,
            timeout=timeout,
            json_mode=json_mode,
        )
    raise ValueError(f"Unknown LLM provider: {provider}")


async def _call_openai_compat(
    prompt: str,
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout: float,
    json_mode: bool,
) -> str:
    """OpenAI-compatible /chat/completions (работает с OpenAI и DeepSeek)."""
    body: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            f"{base_url}/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {api_key}"},
        )
    if r.status_code != 200:
        raise LLMHTTPError(r.status_code, r.text)

    data = r.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"empty choices: {data}")
    return (choices[0].get("message") or {}).get("content") or ""


async def _call_gemini(
    prompt: str,
    *,
    api_key: str,
    model: str,
    timeout: float,
    json_mode: bool,
) -> str:
    """Прямой вызов generativelanguage REST. SDK не нужен."""
    body: dict = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
        },
    }
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent"
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, params={"key": api_key}, json=body)
    if r.status_code != 200:
        raise LLMHTTPError(r.status_code, r.text)

    data = r.json()
    candidates = data.get("candidates") or []
    if not candidates:
        # Часто означает блок safety filter или пустой ответ.
        raise RuntimeError(f"empty gemini candidates: {data}")
    parts = ((candidates[0].get("content") or {}).get("parts")) or []
    if not parts:
        raise RuntimeError(f"empty gemini parts: {data}")
    return parts[0].get("text") or ""
