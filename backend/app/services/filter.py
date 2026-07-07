"""Классификация аудитории вакансии перед сохранением.

Возможные аудитории:
* **teen**    — подходит школьникам 14+ (явные сигналы accept_kids/«от 14»).
* **student** — подходит совершеннолетним (18+), но не школьникам.
* **adult_only** — точно не подходит ни школьникам, ни студентам-новичкам:
  явно требуется опыт ≥1 год, обязательное гражданство РФ или высшее
  образование. Такие вакансии получают **is_hidden=True**.

Аудитория сохраняется через существующее поле ``Vacancy.min_age`` (14 для
teen, 18 для student/adult_only). Фронт фильтрует пользователя по возрасту,
бэк добавит фильтр ``audience == "teen"`` для школьников.

Если фильтр сомневается — выбираем **student** (безопасный дефолт): такая
вакансия скроется от 14-летних, но попадёт в выдачу взрослым.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from ..schemas import VacancyDTO

Audience = Literal["teen", "student", "adult_only"]


@dataclass(frozen=True)
class AudienceClassification:
    audience: Audience
    min_age: int                  # 14 (teen) или 18 (student / adult_only)
    hidden_reason: str | None     # причина скрытия для adult_only

    @property
    def is_hidden(self) -> bool:
        return self.audience == "adult_only"


# ── Сигналы «подходит школьникам» ──────────────────────────────────────────
# Ловим «от 14/15/16», «14+/16+», «школьник», «accept_kids», «для подростков».
# NB: «подросток» в косвенных падежах теряет -о- (подростк-у/-ам/-ами),
# поэтому корень без -ок.
_RE_TEEN_FRIENDLY = re.compile(
    r"(?:"
    r"\bот\s+1[4-6]\s*(?:лет|год)"
    r"|\b1[4-6]\s*\+"
    r"|\b(?:школьник|подростк|несовершеннолетн)"
    r"|\bдля\s+школьник"
    r"|accept[\s_-]?kids"
    r")",
    re.IGNORECASE,
)

# ── Сигналы 18+ (доступно студентам, но не школьникам) ────────────────────
_RE_AGE_18_PLUS = re.compile(
    r"(?:"
    r"\bот\s+1[89]\s*(?:лет|год)"
    r"|\b1[89]\s*\+"
    r"|\b(?:только|строго|исключительно)"
    r"\s+(?:совершеннолетн|с\s+18)"
    r"|\bс\s+1[89]\s+лет"
    r"|\bдостижение\s+совершеннолетия"
    r"|\bнесовершеннолетн\w*\s+не\s+(?:приним|расс)"
    r")",
    re.IGNORECASE,
)

# ── Возраст 20+/21+ (вряд ли подойдёт даже первокурснику) ─────────────────
_RE_AGE_20_PLUS = re.compile(
    r"(?:"
    r"\bот\s+2\d\s*(?:лет|год)"
    r"|\b2\d\s*\+"
    r"|\bс\s+2\d\s+лет"
    r")",
    re.IGNORECASE,
)

# ── Опыт ≥ 1 год ────────────────────────────────────────────────────────────
_RE_EXPERIENCE = re.compile(
    r"(?:опыт(?:\s+работы)?|стаж)"
    r"[^а-яё\d]{0,40}"
    r"(?:от|более|не\s+менее|свыше)?"
    r"\s*(\d+)\s*(?:год|лет)",
    re.IGNORECASE,
)
_RE_EXPERIENCE_NEG = re.compile(
    r"(?:без\s+опыт|опыт\s+(?:не\s+(?:обязател|требу|важен)|необязател))",
    re.IGNORECASE,
)

# ── Обязательное гражданство РФ ────────────────────────────────────────────
_RE_CITIZENSHIP_REQUIRED = re.compile(
    r"(?:"
    r"только\s+граждан(?:е|ам|ин)"
    r"|гражданств[оа]\s+(?:РФ|России)[^.]{0,30}\b(?:обязательн|строго|только)"
    r")",
    re.IGNORECASE,
)

# ── Высшее образование обязательно ────────────────────────────────────────
_RE_HIGHER_ED = re.compile(r"высшее\s+образование", re.IGNORECASE)
_RE_HIGHER_ED_NEG = re.compile(
    r"(?:"
    r"неполное\s+высшее"
    r"|высшее\s+(?:образование\s+)?(?:не\s+обязательн|необязательн|не\s+требуется)"
    r")",
    re.IGNORECASE,
)

# ── Реферальные схемы / MLM ───────────────────────────────────────────────
# ВАЖНО: только железобетонные маркеры. Слова вроде «партнёр», «подключим»,
# «регистрация» встречаются в легитимных вакансиях ритейла (Магнит, Ашан,
# настоящий Самокат) — на них regex давал массу false positives.
# Здесь только формулировки, которые в нормальной вакансии практически
# не встречаются: явное «приведи друга», «реферальная ссылка/программа».
# Всё остальное — на совести LLM-модератора (промпт усилен).
_RE_REFERRAL_SCHEME = re.compile(
    r"(?:"
    r"реферальн\w*\s+(?:ссылк|программ|систем|выплат|бонус|вознагражд)"
    r"|реф[-\s]?ссылк"
    r"|привед[иё]\s+друг|пригласи\s+друг|приглас\w+\s+друз"
    r"|бонус\s+за\s+(?:приглаш|привед[её]нн|друг)"
    r"|зараб\w+\s+на\s+приглаш"
    r"|MLM|сетевой\s+маркетинг"
    r")",
    re.IGNORECASE,
)


def is_referral_scheme(dto: VacancyDTO) -> bool:
    """True, если вакансия похожа на реферальную схему / посредника-вербовщика.

    Используется в ingest как локальная (бесплатная, мгновенная) модерация
    поверх LLM-модератора — она ловит типовые формулировки реф-схем, на
    которых LLM иногда промахивается.
    """
    text = " ".join(
        filter(None, [dto.title or "", dto.company or "", dto.description or ""])
    )
    return bool(_RE_REFERRAL_SCHEME.search(text))


def classify_audience(dto: VacancyDTO) -> AudienceClassification:
    """Определяет аудиторию вакансии.

    Порядок проверок (от жёстких к мягким):
    1. adult_only — опыт ≥1, гражданство, высшее, возраст 20+.
    2. student    — явное 18+ без блокирующих сигналов.
    3. teen       — явные подростковые сигналы (14+, школьник).
    4. teen       — DTO принёс ``min_age <= 16`` (источник пометил сам).
    5. student    — безопасный дефолт.
    """
    text = " ".join(filter(None, [dto.title or "", dto.description or ""]))

    # 1) Жёсткие стопы → adult_only
    if _RE_AGE_20_PLUS.search(text):
        return AudienceClassification("adult_only", 18, "age_20_plus")

    if not _RE_EXPERIENCE_NEG.search(text):
        m = _RE_EXPERIENCE.search(text)
        if m:
            try:
                years = int(m.group(1))
            except (TypeError, ValueError):
                years = 0
            if years >= 1:
                return AudienceClassification("adult_only", 18, f"experience_{years}y")

    if _RE_CITIZENSHIP_REQUIRED.search(text):
        return AudienceClassification("adult_only", 18, "citizenship_required")

    if _RE_HIGHER_ED.search(text) and not _RE_HIGHER_ED_NEG.search(text):
        return AudienceClassification("adult_only", 18, "higher_education_required")

    # 2) Явное 18+ без блокирующих сигналов → student
    if _RE_AGE_18_PLUS.search(text):
        return AudienceClassification("student", 18, None)

    # 3) Явный подростковый сигнал → teen
    if _RE_TEEN_FRIENDLY.search(text):
        return AudienceClassification("teen", 14, None)

    # 4) Парсер источника уже выставил min_age ≤ 16 — доверяем.
    if dto.min_age and dto.min_age <= 16:
        return AudienceClassification("teen", 14, None)

    # 5) Безопасный дефолт.
    return AudienceClassification("student", 18, None)
