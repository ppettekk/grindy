"""Парсинг → AI-модерация → upsert в БД."""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Vacancy, VacancyFormat, VacancySource
from ..parsers import ALL_PARSERS
from ..schemas import VacancyDTO
from .categorize import detect_category
from .filter import classify_audience
from .llm_classify import LLMClassifier, is_ambiguous
from .moderation import moderator

logger = logging.getLogger(__name__)


async def run_ingest(session: AsyncSession, *, per_source_limit: int = 50) -> dict:
    """Запускает все парсеры и сохраняет новые вакансии с AI-модерацией.

    Классификатор аудитории (services.filter.classify_audience) выставляет
    одно из трёх значений: teen / student / adult_only.
    * teen / student — обычные вакансии, отличаются только min_age (14 vs 18).
    * adult_only    — пишутся с is_hidden=True, в ленту не попадают.

    Возвращает статистику по источникам.
    """
    stats: dict[str, dict[str, int]] = {}
    llm = LLMClassifier()

    for parser_cls in ALL_PARSERS:
        parser = parser_cls()
        s = parser.source
        stats[s] = {
            "fetched": 0,
            "added": 0,
            "teen": 0,
            "student": 0,
            "adult_only": 0,
            "spam": 0,
            "skipped": 0,
            "llm_calls": 0,
            "llm_overrides": 0,
            "llm_errors": 0,
        }
        try:
            items = await parser.fetch(limit=per_source_limit)
        except Exception as e:  # noqa: BLE001
            logger.exception("parser %s failed: %s", s, e)
            await parser.aclose()
            continue
        finally:
            await parser.aclose()

        stats[s]["fetched"] = len(items)

        for dto in items:
            existed = await _exists(session, dto)
            if existed:
                stats[s]["skipped"] += 1
                continue

            # 1) Локальная классификация — почти бесплатная.
            cls_res = classify_audience(dto)
            audience = cls_res.audience
            min_age = cls_res.min_age
            is_hidden = cls_res.is_hidden
            hidden_reason = (
                f"auto:{cls_res.hidden_reason}" if cls_res.is_hidden else None
            )
            category = dto.category or detect_category(dto.title, dto.description)
            llm_classified = False

            # 2) Догон LLM на сомнительных вакансиях.
            ambiguous, _amb_reason = is_ambiguous(dto, cls_res, category)
            if ambiguous and llm.available and llm.budget_left > 0:
                calls_before = llm.calls_used
                errors_before = llm.errors
                llm_res = await llm.classify(dto)
                stats[s]["llm_calls"] += llm.calls_used - calls_before
                stats[s]["llm_errors"] += llm.errors - errors_before

                if llm_res and llm_res.confidence >= llm.min_confidence:
                    audience = llm_res.audience
                    min_age = llm_res.min_age
                    is_hidden = audience == "adult_only"
                    hidden_reason = (
                        f"llm:{llm_res.reason[:80]}" if is_hidden else None
                    )
                    if llm_res.category:
                        category = llm_res.category
                    llm_classified = True
                    stats[s]["llm_overrides"] += 1

            stats[s][audience] += 1

            mod = await moderator.check(dto.title, dto.company, dto.description)
            # is_spam=True только если модератор ЯВНО пометил как спам.
            # Высокая confidence на «не спам» (is_spam=False, conf=1.0)
            # не должна превращаться в spam-флаг — это была старая бага.
            is_spam_flag = bool(mod.is_spam) and mod.confidence >= 0.85
            if is_spam_flag:
                stats[s]["spam"] += 1

            v = Vacancy(
                source=VacancySource(dto.source),
                external_id=dto.external_id,
                title=dto.title,
                company=dto.company,
                description=dto.description,
                salary_from=dto.salary_from,
                salary_to=dto.salary_to,
                salary_unit=dto.salary_unit,
                city=dto.city,
                format=VacancyFormat(dto.format),
                category=category,
                min_age=min_age,
                url=dto.url,
                is_spam=is_spam_flag,
                spam_confidence=mod.confidence,
                spam_reason=mod.reason or None,
                is_hidden=is_hidden,
                hidden_reason=hidden_reason,
                llm_classified=llm_classified,
                posted_at=dto.posted_at,
            )
            session.add(v)
            stats[s]["added"] += 1

        await session.commit()

    return stats


async def _exists(session: AsyncSession, dto: VacancyDTO) -> bool:
    q = select(Vacancy.id).where(
        Vacancy.source == VacancySource(dto.source),
        Vacancy.external_id == dto.external_id,
    )
    res = await session.execute(q)
    return res.scalar_one_or_none() is not None


def is_suspect(confidence: float) -> bool:
    return 0.6 <= confidence < 0.85
