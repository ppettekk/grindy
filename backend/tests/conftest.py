"""Общие фикстуры для тестов."""
import os

# Принудительно SQLite + выкл шедулер для всех тестов.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("RUN_SCHEDULER", "false")
os.environ.setdefault("BOT_TOKEN", "")
os.environ.setdefault("GEMINI_API_KEY", "")
