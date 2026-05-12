"""Пул API-ключей Gemini с авторотацией."""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Literal

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
class GeminiKeyPool:
    """Round-robin пул ключей с маркировкой нерабочих."""

    entries: list[KeyEntry] = field(default_factory=list)
    idx: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def from_settings(cls) -> "GeminiKeyPool":
        return cls(entries=[KeyEntry(k) for k in settings.gemini_keys])

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
                "Gemini key %s disabled (%s); active=%d/%d",
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


# ── Классификация ошибок Gemini ───────────────────────────────────────────


_RATE_LIMIT_PATTERNS = re.compile(
    r"(?:resource[\s_-]?exhausted|429|quota|rate[\s_-]?limit|too\s+many\s+requests)",
    re.IGNORECASE,
)
_KEY_INVALID_PATTERNS = re.compile(
    r"(?:permission[\s_-]?denied|unauthenticated|api\s+key\s+not\s+valid"
    r"|invalid\s+api\s+key|api[\s_-]?key[\s_-]?invalid|401|403)",
    re.IGNORECASE,
)


def classify_error(err: BaseException):
    """Возвращает 'quota' / 'invalid_key' / None."""
    msg = f"{type(err).__name__}: {err}"
    if _KEY_INVALID_PATTERNS.search(msg):
        return "invalid_key"
    if _RATE_LIMIT_PATTERNS.search(msg):
        return "quota"
    return None


# ── Process-level singleton ───────────────────────────────────────────────


_pool: "GeminiKeyPool | None" = None
_pool_lock = threading.Lock()


def get_pool() -> GeminiKeyPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = GeminiKeyPool.from_settings()
                logger.info(
                    "Gemini key pool initialised with %d key(s)",
                    _pool.total_count,
                )
    return _pool


def reset_pool_for_testing() -> None:
    """Сброс синглтона. Используется только тестами."""
    global _pool
    _pool = None
