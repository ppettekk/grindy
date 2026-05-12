"""Тесты для категоризации и определения min_age по тексту вакансии."""
from __future__ import annotations

import pytest

from app.parsers.base import BaseParser
from app.services.categorize import detect_categories, detect_category

detect_min_age = BaseParser.detect_min_age


# ── detect_category — основные категории ──────────────────────────────────

@pytest.mark.parametrize(
    "title,description,expected",
    [
        ("Курьер по доставке еды", "", "Курьерская доставка"),
        ("Бариста в кофейню", "", "Фастфуд и общепит"),
        ("Промоутер с раздачей листовок", "", "Промо и раздача"),
        ("Кассир в магазин", "", "Кассир и торговля"),
        ("Упаковщик на склад", "", "Сборщик/упаковщик"),
        ("Грузчик-комплектовщик", "", "Грузчик и склад"),
        ("Уборщица в офис", "", "Уборка"),
        ("Аниматор на детский праздник", "", "Аниматор"),
        ("Репетитор по математике", "", "Репетитор и обучение"),
        ("Оператор колл-центра", "", "Колл-центр и онлайн"),
        ("SMM-менеджер для бренда", "", "Контент и SMM"),
        ("Копирайтер на удалёнку", "", "Копирайтинг"),
        ("Веб-дизайнер начинающий", "", "Дизайн и графика"),
        ("Помощник руководителя", "", "Помощник и ассистент"),
        ("Стажёр-разработчик", "", "Стажировки"),
        ("Тайный покупатель в магазине", "", "Тайный покупатель"),
        ("Водитель-курьер на личном авто", "", "Развоз на авто"),
    ],
)
def test_detect_category_by_title(title, description, expected):
    assert detect_category(title, description) == expected


def test_detect_category_none_when_no_match():
    assert detect_category("Просто работа", "Интересная и весёлая") is None


def test_detect_category_uses_description_as_fallback():
    # В title нет ключевого слова, в description есть → должна сработать.
    assert (
        detect_category("Срочно", "Раздача листовок в центре города")
        == "Промо и раздача"
    )


def test_detect_category_title_weighs_more():
    """При конкуренции категорий в title и description побеждает title."""
    # title матчит «Уборка», description — «Курьерская доставка».
    cat = detect_category("Уборщик помещений", "Иногда подрабатываем доставкой еды")
    assert cat == "Уборка"


def test_detect_categories_returns_all_matches():
    cats = detect_categories(
        "Курьер на самокате",
        "Также возможна работа в кафе (бариста)",
    )
    assert "Курьерская доставка" in cats
    assert "Фастфуд и общепит" in cats


# ── detect_min_age — числовые паттерны ────────────────────────────────────

@pytest.mark.parametrize(
    "text,expected",
    [
        ("Работа от 14 лет, школьникам подойдёт", 14),
        ("16+ возраст, без опыта", 16),
        ("От 18 лет, желателен опыт", 18),
        ("Принимаем с 16 лет на работу", 16),
        ("Трудоустройство с 14, школьникам можно", 14),
        ("Возраст: 16-25 лет", 16),
        ("От 18 до 35 лет, работа в офисе", 18),
        ("Школьник, ищем помощника", 14),
        ("Подросткам подойдёт", 14),
        ("Только совершеннолетним, оформление по ТК", 18),
        ("Несовершеннолетним нельзя, безопасность", 18),
        # Дефолт при отсутствии сигналов.
        ("Курьер для доставки документов", 16),
        # Несколько триггеров → берём минимум.
        ("От 18 лет, но школьникам тоже можно", 14),
    ],
)
def test_detect_min_age(text, expected):
    assert detect_min_age(text) == expected


def test_detect_min_age_empty_string():
    assert detect_min_age("") == 16


def test_detect_min_age_ignores_salary_numbers():
    """В строке «зарплата 50000 руб» не должно сработать как min_age=50."""
    assert detect_min_age("Курьер, зарплата 50000 руб в месяц") == 16
