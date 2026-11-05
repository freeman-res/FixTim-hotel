"""Выбирает действие, не требуя дату/город для каждого сообщения.

Пока без второго LLM-вызова: использует намерение из TripPatch и несколько
явных формулировок для защиты от неверной классификации.
"""
import re
from .schemas import TripPatch, Intent


class IntentRouter:
    @staticmethod
    def detect(message: str, patch: TripPatch, state: dict) -> Intent:
        text = message.casefold().strip()
        trip = state.get("trip", {})

        if re.search(r"\b(оформ|бронируй|забронируй|оплат|подтверждаю заказ)", text):
            return "checkout"
        if re.search(r"(собери поездку|план поездки|составь маршрут|собери маршрут|собери корзину)", text):
            return "itinerary"
        if re.search(r"\b(сравни|сравнить|сравнение|чем отлича)", text):
            return "compare"
        if re.search(r"(расскажи.*(отел|гостиниц|вариант)|подробн.*(отел|вариант)|покажи.*(отел|вариант)|посмотри.*(отел|вариант))", text):
            return "details"
        if state.get("last_hotel_ids") and re.search(r"(расскажи|посмотри|подробн|покажи)", text) and IntentRouter.referenced_hotel_number(message):
            return "details"
        if re.search(r"(куда-нибудь|куда поехать|куда лучше поехать|не знаю куда|выбери направление|предложи направление|посоветуй направление)", text):
            return "inspiration"
        if ("на море" in text or "к морю" in text) and not re.search(r"(отел|гостиниц)", text):
            return "inspiration"
        if "крым" in text and not re.search(r"(отел|гостиниц)", text):
            return "inspiration"
        if re.search(r"(погод|температур|климат|осадк|дожд|снег|жарк|холодн)", text):
            return "weather"
        if not trip.get("city") and any(w in text for w in ("на море", "к морю", "отдохнуть", "для отдыха")):
            return "inspiration"
        if patch.reject_hotel_ids or patch.reject_result_numbers:
            return "hotel_search"
        if state.get("needs_replan") and (patch.shift_days is not None or state.get("changed_fields")):
            return "replan"
        if re.search(r"(дорог|добрат|маршрут|перел[её]т|билет|поезд|автобус|транспорт|рейс)", text):
            return "trip_search"
        if state.get("selected_hotel") and text in {"завтра", "послезавтра"}:
            return "trip_search"
        if state.get("last_intent") == "trip_search" and text.rstrip("\\") in {"да", "предпочтений нет", "без предпочтений"}:
            return "trip_search"
        if state.get("last_intent") == "trip_search" and patch.shift_days is not None:
            return "trip_search"
        if state.get("last_intent") == "trip_search" and (patch.origin_city or re.match(r"^из\s+", text)):
            return "trip_search"
        if patch.intent is not None:
            return patch.intent
        if any(w in text for w in ("самолет", "самолёт", "перелёт", "билет", "поезд", "автобус", "транспорт", "как добраться", "рейс", "дорога туда")):
            return "trip_search"
        if state.get("itinerary") and state.get("changed_fields"):
            return "replan"
        if any(w in text for w in ("отел", "гостиниц", "номера", "найди", "подбери")):
            return "hotel_search"
        if state.get("changed_fields") and trip.get("city"):
            return "hotel_search"
        return "chat"

    @staticmethod
    def referenced_hotel_number(message: str) -> int | None:
        """Разрешает «первый/2-й отель» по сохранённым last_hotel_ids."""
        text = message.casefold()
        words = {"перв": 1, "втор": 2, "трет": 3, "четверт": 4, "пят": 5}
        for stem, number in words.items():
            if re.search(rf"\b{stem}\w*\b", text):
                return number
        match = re.search(r"\b([1-5])\s*(?:-й|-ый|-ий)?\s*(?:отел|вариант|гостиниц)", text)
        return int(match.group(1)) if match else None
