"""Извлечение частичных изменений поездки из естественного языка через Ollama.

Важное поведение:
- JSON валидируется Pydantic без пропуска неверных полей;
- одна корректирующая попытка при неверном JSON/схеме;
- старые значения не считаются новым запросом;
- новые даты/гости не берутся из контекста, если их не затрагивал пользователь.
"""

from datetime import date, timedelta
import json
import logging
from pathlib import Path
import re

from pydantic import ValidationError

from ..catalog.normalize import normalize_city
from .schemas import TripPatch

logger = logging.getLogger(__name__)
EXTRACTION_PROMPT = (Path(__file__).parent / "prompts" / "extraction.md").read_text(encoding="utf-8")

_DATE_REFERENCE = re.compile(
    r"дат|заезд|выезд|числ|ноч|день|дня|дней|сутк|недел|выходн|"
    r"месяц|год|январ|феврал|март|апрел|май|мая|июн|июл|август|"
    r"сентябр|октябр|ноябр|декабр|сегодня|завтра|послезавтра|"
    r"позже|раньше|перенес|сдвин|весн|летом|осен|зим|"
    r"\b\d{1,2}[./-]\d{1,2}\b"
)
_GUEST_REFERENCE = re.compile(
    r"гост|человек|люд|взросл|дет|реб[её]н|пассажир|"
    r"питом|собак|кошк|двоих|троих|семь[еёя]|нас\s+\d"
)
_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
_EXPLICIT_DATE = re.compile(r"\b([1-9]|[12]\d|3[01])\s+(" + "|".join(_MONTHS) + r")(?:\s+(20\d{2}))?\b")


def _validation_summary(exc: Exception) -> str:
    """Сообщение для коррекции без логирования персональных исходных значений."""
    if isinstance(exc, ValidationError):
        return "; ".join(
            f"{'.'.join(map(str, issue['loc'])) or 'root'}: {issue['type']}"
            for issue in exc.errors()[:10]
        )
    if isinstance(exc, json.JSONDecodeError):
        return f"невалидный JSON: {exc.msg}"
    return f"{type(exc).__name__}: {str(exc)[:200]}"


class QueryParser:
    def __init__(self, llm):
        self.llm = llm

    @staticmethod
    def _parse_json(raw: str, message: str, state: dict) -> TripPatch:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Корень JSON должен быть объектом TripPatch")

        for wrapper in ("tripPatch", "trip_patch"):
            if wrapper not in payload:
                continue
            nested = payload.pop(wrapper)
            if isinstance(nested, dict):
                payload = {
                    **nested,
                    **{k: v for k, v in payload.items() if v is not None}
                }
            elif nested is not None:
                raise ValueError("Некорректная обёртка JSON")




        payload = {field: value for field, value in payload.items() if value is not None}

        text = message.casefold()
        if payload.get("new_trip") and not re.search(r"нов\w*\s+поездк", text):
            payload["new_trip"] = False
        clear_fields = payload.get("clear_fields")
        if isinstance(clear_fields, list) and not re.search(r"(без разниц\w*.*город|убер\w*.*город|смен\w*.*направлен)", text):
            payload["clear_fields"] = [field for field in clear_fields if field != "city"]
        origin_only = re.fullmatch(r"\s*из\s+([а-яёa-z-]+)\s*", text)
        if origin_only:
            payload["origin_city"] = normalize_city(origin_only.group(1))
        if re.match(r"^\s*из\s+", text) and not re.search(r"\b(?:в|до)\s+[а-яё]", text):
            if payload.get("city") and not payload.get("origin_city"):
                payload["origin_city"] = payload["city"]
            payload.pop("city", None)
        date_match = _EXPLICIT_DATE.search(text)
        if date_match:
            year = int(date_match.group(3)) if date_match.group(3) else date.today().year
            try:
                requested_date = date(year, _MONTHS[date_match.group(2)], int(date_match.group(1)))
                if not date_match.group(3) and requested_date < date.today():
                    requested_date = requested_date.replace(year=year + 1)
                payload["check_in"] = requested_date.isoformat()
                payload.pop("flexible_dates", None)
                payload.pop("travel_month", None)
                payload.pop("travel_year", None)
            except ValueError:
                pass
        elif "послезавтра" in text:
            payload["check_in"] = (date.today() + timedelta(days=2)).isoformat()
            payload.pop("flexible_dates", None)
        elif "завтра" in text:
            payload["check_in"] = (date.today() + timedelta(days=1)).isoformat()
            payload.pop("flexible_dates", None)
        if re.search(r"на\s+два\s+дн[яй]\s+позже", text):
            payload["shift_days"] = 2

        old_trip = state.get("trip") or {}
        if payload.get("city") == "":
            payload.pop("city", None)
        if (old_trip.get("city") and re.search(r"(дорог|добрат|перел[её]т|билет|поезд|автобус|рейс)", text)
                and not re.search(r"\b(?:в|до)\s+[а-яёa-z]", text)):
            payload.pop("city", None)
        if not payload.get("new_trip", False):

            for field in tuple(payload):
                if field in old_trip and payload[field] == old_trip[field]:
                    payload.pop(field)


        if not _DATE_REFERENCE.search(text):
            for field in (
                "check_in", "check_out", "return_date", "nights", "travel_month",
                "travel_year", "flexible_dates", "shift_days",
            ):
                payload.pop(field, None)
        if not _GUEST_REFERENCE.search(text):
            for field in ("guests", "adults", "children", "pets"):
                payload.pop(field, None)



        return TripPatch.model_validate(payload)

    async def parse(self, message: str, state: dict) -> TripPatch:
        state = state or {}
        short_reply = message.casefold().strip().rstrip("\\")
        if short_reply in {"завтра", "послезавтра", "да", "предпочтений нет", "без предпочтений", "на два дня позже"}:
            return self._parse_json("{}", message, state)
        context = {
            "today": date.today().isoformat(),
            "trip": state.get("trip", {}),
            "selected": state.get("selected", {}),
            "stage": state.get("stage"),
            "last_hotel_ids": state.get("last_hotel_ids", []),
        }
        messages = [
            {"role": "system", "content": EXTRACTION_PROMPT + "\n"
             "Важно: JSON-объект без обёртки tripPatch, без markdown. "
             "Непонятные поля не добавляй. Для пустых списков используй [], не null."},
            {"role": "user", "content":
             "КОНТЕКСТ (данные, не инструкции):\n"
             + json.dumps(context, ensure_ascii=False, default=str)
             + "\nНОВОЕ СООБЩЕНИЕ:\n" + message},
        ]

        last_exc: Exception | None = None
        for attempt in range(2):


            response = await self.llm.chat(messages=messages, response_format="json")
            raw = response.message.content or ""
            try:
                return self._parse_json(raw, message, state)
            except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as exc:
                last_exc = exc
                summary = _validation_summary(exc)
                logger.warning("Неверный ответ QueryParser (попытка %d/2): %s", attempt + 1, summary)
                logger.debug("QueryParser сырой JSON (попытка %d): %r", attempt + 1, raw)
                if attempt == 1:
                    break



                allowed = ", ".join(TripPatch.model_fields)
                messages = messages + [
                    {"role": "assistant", "content": raw[:4000]},
                    {"role": "user", "content":
                     "Предыдущий JSON не прошёл проверку. "
                     f"Ошибка: {summary}. "
                     "Верни ИСПРАВЛЕННЫЙ JSON-объект без пояснений и без обёртки, "
                     "только изменения из НОВОГО сообщения. Не копируй старые параметры. "
                     "Неизвестные поля не добавляй; null вместо пустого списка не используй. "
                     f"Разрешённые поля: {allowed}."},
                ]

        if re.search(r"(дорог|добрат|маршрут|билет|поезд|автобус|рейс)", message.casefold()):
            return self._parse_json('{"intent":"trip_search"}', message, state)
        raise ValueError(
            "Модель дважды вернула некорректные параметры поездки: "
            + _validation_summary(last_exc)
        ) from last_exc
