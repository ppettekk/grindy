"""Backward-compat shim. Используйте app.services.llm_keys."""
from .llm_keys import (  # noqa: F401
    KeyEntry,
    LLMKeyPool as GeminiKeyPool,
    classify_error,
    get_pool,
    reset_pool_for_testing,
)

__all__ = [
    "KeyEntry",
    "GeminiKeyPool",
    "classify_error",
    "get_pool",
    "reset_pool_for_testing",
]
