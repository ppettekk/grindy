"""Trudvsem.ru — открытое API госпортала «Работа России».

Документация: https://trudvsem.ru/opendata/api
Endpoint: http://opendata.trudvsem.ru/api/v1/vacancies
- Без авторизации.
- Лимит ≤ 100 записей на запрос (offset/limit-пагинация).
- Зарплата — `salary_min`/`salary_max`, всегда в рублях.
- Не банит DC-IP, можно с любого хостинга.

Использование: один из основных источников вакансий для проекта.
"""
from __future__ import annotations

import logging
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from ..schemas import VacancyDTO
from .base import BaseParser

logger = logging.getLogger(__name__)


# Широкие запросы, под которые попадают сотни релевантных профессий.
# Мы НЕ хардкодим «бариста/курьер» — это слишком узко и пропускает кучу
# подходящего (упаковщики, флаерщики, расклейщики, разнорабочие и т.д.).
# Локально потом фильтруем по requirement.experience==0 и постфильтром
# is_suitable_for_teen.
TRUDVSEM_QUERIES = [
    "подработка",
    "без опыта",
    "школьник",
    "студент",
    "стажёр",
    "помощник",
    "ученик",
    "стажировка",
]


# Региональные запросы: endpoint /region/{ОКАТО-код} отдаёт вакансии
# конкретного субъекта. Без этого Москва/Питер тонут в общероссийской
# выдаче. Коды ОКАТО городов федерального значения и крупнейших агломераций.
TRUDVSEM_REGIONS: dict[str, str] = {
    "Москва": "45000000000",
    "Санкт-Петербург": "40000000000",
    "Московская область": "46000000000",
    "Ленинградская область": "41000000000",
    "Новосибирская область": "50000000000",
    "Свердловская область": "65000000000",
    "Республика Татарстан": "92000000000",
    "Краснодарский край": "03000000000",
    "Нижегородская область": "22000000000",
    "Ростовская область": "60000000000",
}


# Берём только вакансии «без опыта». Поле requirement.experience приходит
# числом — 0 значит «не требуется». Иногда приходит строкой/None — считаем
# как 0 (т.е. пропускаем), чтобы не отбрасывать вакансии без явного значения.
def _requires_experience(item: dict) -> bool:
    req = item.get("requirement")
    if not isinstance(req, dict):
        return False
    exp = req.get("experience")
    if exp in (None, "", 0, "0"):
        return False
    try:
        return int(float(exp)) >= 1
    except (TypeError, ValueError):
        return False


class TrudvsemParser(BaseParser):
    source = "trudvsem"
    BASE_URL = "https://opendata.trudvsem.ru/api/v1/vacancies"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _search(self, text: str, offset: int = 0, limit: int = 30) -> dict:
        """Общероссийский поиск по тексту."""
        params = {"text": text, "offset": offset, "limit": min(limit, 100)}
        r = await self.client.get(self.BASE_URL, params=params)
        r.raise_for_status()
        return r.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _search_region(
        self, region_code: str, text: str, offset: int = 0, limit: int = 50
    ) -> dict:
        """Поиск по конкретному региону (ОКАТО-код)."""
        params = {"text": text, "offset": offset, "limit": min(limit, 100)}
        r = await self.client.get(
            f"{self.BASE_URL}/region/{region_code}", params=params
        )
        r.raise_for_status()
        return r.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _search_modified(
        self, since_iso: str, offset: int = 0, limit: int = 100
    ) -> dict:
        """Дельта-запрос: вакансии, изменённые после ``since_iso`` (ISO-8601).

        Это даёт настоящий поток свежих вакансий: на каждом ingest-цикле
        новые публикации, а не один и тот же топ-50.
        """
        params = {
            "modifiedFrom": since_iso,
            "offset": offset,
            "limit": min(limit, 100),
        }
        r = await self.client.get(f"{self.BASE_URL}/modified", params=params)
        r.raise_for_status()
        return r.json()

    def _ingest_response(
        self,
        data: dict,
        *,
        out: list[VacancyDTO],
        seen: set[str],
        limit: int,
    ) -> int:
        """Парсит ответ API в out (in-place). Возвращает число skipped по опыту."""
        skipped = 0
        vacancies = (data.get("results") or {}).get("vacancies") or []
        for wrapper in vacancies:
            item = wrapper.get("vacancy") if isinstance(wrapper, dict) else None
            if not isinstance(item, dict):
                continue
            ext_id = str(item.get("id") or "")
            if not ext_id or ext_id in seen:
                continue
            seen.add(ext_id)
            if _requires_experience(item):
                skipped += 1
                continue
            dto = self._map(item)
            if dto is None:
                continue
            out.append(dto)
            if len(out) >= limit:
                break
        return skipped

    async def fetch(self, *, limit: int = 50) -> list[VacancyDTO]:
        out: list[VacancyDTO] = []
        seen: set[str] = set()
        skipped_exp = 0

        # /modified endpoint у Trudvsem не существует (404) — проверено вживую.
        # Источник свежака — только региональные запросы (см. ниже) + offset.
        # Чтобы получать больше уникальных вакансий, пагинируем по регионам.

        # 1) Региональные запросы — приоритет крупным городам, чтобы лента
        #    не была общероссийской кашей. Пагинируем по 2-3 страницы на регион
        #    через offset — это даёт больше уникальных вакансий каждый ingest.
        for region_name, code in TRUDVSEM_REGIONS.items():
            if len(out) >= limit * 6:
                break
            for offset in (0, 100, 200):
                try:
                    data = await self._search_region(
                        code, "подработка", offset=offset, limit=100
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "trudvsem region %s (%s) offset=%d failed: %s",
                        region_name, code, offset, e,
                    )
                    break
                before = len(out)
                skipped_exp += self._ingest_response(
                    data, out=out, seen=seen, limit=limit * 6
                )
                # Если страница ничего не добавила — следующая бесполезна,
                # значит регион пуст / выдача закончилась.
                if len(out) == before:
                    break
                if len(out) >= limit * 6:
                    break

        # 2) Общероссийские текстовые запросы — добивают мелкие города.
        per_query = max(30, limit)
        for q in TRUDVSEM_QUERIES:
            if len(out) >= limit * 5:
                break
            try:
                data = await self._search(q, offset=0, limit=per_query)
            except Exception as e:  # noqa: BLE001
                logger.warning("trudvsem fetch failed for %r: %s", q, e)
                continue
            skipped_exp += self._ingest_response(
                data, out=out, seen=seen, limit=limit * 5
            )

        if skipped_exp:
            logger.info(
                "trudvsem: skipped %d vacancies (experience required)", skipped_exp
            )
        if not out:
            logger.info("TrudvsemParser: ничего не получено.")
        return out

    def _map(self, item: dict[str, Any]) -> VacancyDTO | None:
        title = (item.get("job-name") or "").strip()
        if not title:
            return None

        ext_id = str(item.get("id") or "")
        if not ext_id:
            return None

        company = ((item.get("company") or {}).get("name") or "").strip() or None
        region = ((item.get("region") or {}).get("name") or "").strip() or None
        # Нормализуем «г. Москва» / «Московская область, г. Дмитров» → ведущее значимое слово.
        city = self._extract_city(region, item)

        duty = (item.get("duty") or "").strip()
        req_raw = item.get("requirement")
        req_text = ""
        if isinstance(req_raw, dict):
            req_text = " ".join(
                str(v) for v in req_raw.values() if v and isinstance(v, (str, int))
            )
        elif isinstance(req_raw, str):
            req_text = req_raw

        description = (duty + ("\n\n" + req_text if req_text else "")).strip() or None

        salary_from = _safe_int(item.get("salary_min"))
        salary_to = _safe_int(item.get("salary_max"))

        schedule_text = (item.get("schedule") or "").lower()
        employment = (item.get("employment") or "").lower()
        remote = "удалён" in schedule_text or "дистанц" in schedule_text \
            or "удалён" in employment or "дистанц" in employment
        fmt = "online" if remote else "offline"

        url = (item.get("vac_url") or "").strip()
        if not url:
            company_code = (item.get("company") or {}).get("companycode") or ""
            if company_code and ext_id:
                # Эмулируем стандартный URL trudvsem на случай отсутствия vac_url.
                url = f"https://trudvsem.ru/vacancy/card/{company_code}/{ext_id}"
        if not url:
            return None

        text_for_age = " ".join(filter(None, [title, duty, req_text]))

        return VacancyDTO(
            source="trudvsem",
            external_id=ext_id,
            title=title,
            company=company,
            description=description,
            salary_from=salary_from,
            salary_to=salary_to,
            salary_unit="/мес",
            city=city,
            format=fmt,
            category=None,
            min_age=self.detect_min_age(text_for_age),
            url=url,
            posted_at=item.get("creation-date"),
        )

    @staticmethod
    def _extract_city(region: str | None, item: dict[str, Any]) -> str | None:
        """Достаёт «человеческое» название города из вакансии Trudvsem.

        Стратегия:
        1. Перебираем `addresses.address[*].location` — у части вакансий это
           конкретный адрес вида «г. Дмитров, ул. Ленина, 5». Берём первую
           часть до запятой и очищаем.
        2. Резерв — `region.name` (для городов федерального значения это
           «г. Москва», для остальных — «Московская область»).
        """
        addresses = (item.get("addresses") or {}).get("address")
        if isinstance(addresses, list):
            for a in addresses:
                if not isinstance(a, dict):
                    continue
                loc = a.get("location")
                if not isinstance(loc, str) or not loc.strip():
                    continue
                city = _clean_city_name(loc.split(",")[0])
                if city:
                    return city

        if region:
            city = _clean_city_name(region)
            if city:
                return city
        return None


def _clean_city_name(raw: str) -> str | None:
    """Чистит имя города от префиксов 'г.'/'город' и суффиксов 'обл./область'.

    Примеры:
      'г. Москва'                → 'Москва'
      'г.Санкт-Петербург'        → 'Санкт-Петербург'
      'город Дмитров'            → 'Дмитров'
      'Московская область'       → 'Московская область'  (оставляем как есть)
      'Санкт-Петербург, Невский' → 'Санкт-Петербург'
    """
    import re as _re

    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    # Срезаем «г. » / «г.» / «город » в начале.
    s = _re.sub(r"^(?:г\.?\s*|город\s+|гор\.\s*)", "", s, flags=_re.IGNORECASE)
    # Если осталась запятая (адрес внутри уже расщеплён, но на всякий) — первая часть.
    s = s.split(",")[0].strip()
    # Хвостовые знаки и лишние пробелы.
    s = _re.sub(r"\s+", " ", s).strip(" .,;")
    return s or None


def _safe_int(x: Any) -> int | None:
    if x in (None, "", 0, "0"):
        return None
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None
