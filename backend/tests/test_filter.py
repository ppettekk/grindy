"""Тесты для services.filter.classify_audience.

Покрываем три основных исхода (teen/student/adult_only) и часть граничных
случаев — что фильтр не путает «без опыта» с «опыт от N лет», правильно
относится к 18+/20+ и т.п.
"""
from __future__ import annotations

import pytest

from app.schemas import VacancyDTO
from app.services.filter import classify_audience


def _make(title: str, description: str = "", **kw) -> VacancyDTO:
    return VacancyDTO(
        source=kw.pop("source", "trudvsem"),
        external_id=kw.pop("external_id", "test-1"),
        title=title,
        description=description,
        url=kw.pop("url", "https://example.com/v/1"),
        min_age=kw.pop("min_age", 14),
        **kw,
    )


# ── teen ───────────────────────────────────────────────────────────────────

def test_teen_explicit_14_plus():
    dto = _make("Курьер", "Берём от 14 лет, без опыта работы")
    res = classify_audience(dto)
    assert res.audience == "teen"
    assert res.min_age == 14
    assert res.hidden_reason is None


def test_teen_keyword_schoolboy():
    dto = _make("Промоутер", "Подойдёт школьникам, гибкий график")
    res = classify_audience(dto)
    assert res.audience == "teen"


def test_teen_from_dto_min_age():
    # Тест с пустым описанием: классификатор должен довериться dto.min_age.
    dto = _make("Курьер", "", min_age=14)
    res = classify_audience(dto)
    assert res.audience == "teen"


# ── student ────────────────────────────────────────────────────────────────

def test_student_age_18_plus():
    dto = _make("Бариста", "Работа от 18 лет, без опыта, гибкий график")
    res = classify_audience(dto)
    assert res.audience == "student"
    assert res.min_age == 18


def test_student_default_when_no_signals():
    # Нет явных сигналов И источник не пометил min_age как подростковый.
    # Ожидаем безопасный дефолт — student.
    dto = _make("Помощник", "Несложная работа в офисе", min_age=18)
    res = classify_audience(dto)
    assert res.audience == "student"


# ── adult_only ─────────────────────────────────────────────────────────────

def test_adult_only_experience_required():
    dto = _make("Старший менеджер", "Опыт работы от 3 лет обязателен")
    res = classify_audience(dto)
    assert res.audience == "adult_only"
    assert res.hidden_reason is not None and res.hidden_reason.startswith("experience_")


def test_adult_only_age_20_plus():
    dto = _make("Курьер", "От 25 лет, водительские права")
    res = classify_audience(dto)
    assert res.audience == "adult_only"
    assert res.hidden_reason == "age_20_plus"


def test_adult_only_citizenship():
    dto = _make("Грузчик", "Только граждане РФ, оформление по ТК")
    res = classify_audience(dto)
    assert res.audience == "adult_only"
    assert res.hidden_reason == "citizenship_required"


def test_adult_only_higher_education():
    dto = _make("Стажёр аналитик", "Требуется высшее образование, экономика")
    res = classify_audience(dto)
    assert res.audience == "adult_only"
    assert res.hidden_reason == "higher_education_required"


# ── Граничные кейсы ────────────────────────────────────────────────────────

def test_no_false_positive_without_experience():
    """«Без опыта» НЕ должно трактоваться как «опыт N лет»."""
    dto = _make("Курьер", "Без опыта работы, обучаем на месте")
    res = classify_audience(dto)
    assert res.audience != "adult_only"


def test_no_false_positive_higher_education_not_required():
    dto = _make("Стажёр", "Высшее образование не требуется, главное желание учиться")
    res = classify_audience(dto)
    assert res.audience != "adult_only"


def test_experience_hard_signal_beats_teen_hint():
    """Если есть и «школьник», и «опыт от 2 лет» — побеждает стоп-слово."""
    dto = _make(
        "Промоутер",
        "Подойдёт школьникам. Обязательно: опыт работы от 2 лет",
    )
    res = classify_audience(dto)
    assert res.audience == "adult_only"


# ── is_referral_scheme ─────────────────────────────────────────────────────
# Детектор узкий намеренно: ловит только железобетонные маркеры MLM/реф-схем.
# Лучше пропустить мусор, чем зарубить легитимную вакансию ритейла.


def test_referral_scheme_invite_friend():
    from app.services.filter import is_referral_scheme
    dto = _make("Курьер", "Приведи друга и получи бонус за приглашение 3000 рублей")
    assert is_referral_scheme(dto) is True


def test_referral_scheme_referral_link():
    from app.services.filter import is_referral_scheme
    dto = _make("Работа на дому", "Регистрируйся по реферальной ссылке, доход без вложений")
    assert is_referral_scheme(dto) is True


def test_referral_scheme_referral_program_in_company():
    from app.services.filter import is_referral_scheme
    dto = _make("Курьер", "Доставка еды", company="Реферальная программа Драйв")
    assert is_referral_scheme(dto) is True


def test_referral_scheme_mlm():
    from app.services.filter import is_referral_scheme
    dto = _make("Менеджер", "Сетевой маркетинг, построй свою команду")
    assert is_referral_scheme(dto) is True


# ── НЕ реф-схема: легитимные вакансии не должны помечаться ──────────────────


def test_not_referral_real_samokat():
    """Настоящая вакансия Самоката — НЕ реф-схема."""
    from app.services.filter import is_referral_scheme
    dto = _make("Курьер", "Доставка заказов Самоката, гибкий график, выплаты ежедневно",
                company="Самокат")
    assert is_referral_scheme(dto) is False


def test_not_referral_retail_chain():
    """Магнит / Ашан / Пятёрочка — обычный ритейл, не реф-схема."""
    from app.services.filter import is_referral_scheme
    for company, title, desc in [
        ("Магнит", "Продавец-кассир", "Работа в магазине у дома, оформление по ТК РФ"),
        ("Ашан", "Кассир, подработка", "Гипермаркет, сменный график, обучение на месте"),
        ("Пятёрочка", "Сотрудник магазина", "Выкладка товара, работа с кассой, соцпакет"),
    ]:
        dto = _make(title, desc, company=company)
        assert is_referral_scheme(dto) is False, f"{company} ошибочно помечен"


def test_not_referral_normal_courier():
    from app.services.filter import is_referral_scheme
    dto = _make("Пеший курьер", "Доставка документов по центру, оплата сдельная, обучение")
    assert is_referral_scheme(dto) is False


def test_not_referral_partner_word_alone():
    """Просто слово 'партнёр' или 'подключение' — НЕ повод считать реф-схемой."""
    from app.services.filter import is_referral_scheme
    dto = _make("Курьер-партнёр", "Подключим к сервису за 10 минут, выплаты ежедневно")
    # Узкий детектор это пропускает — на совести LLM-модератора.
    assert is_referral_scheme(dto) is False
