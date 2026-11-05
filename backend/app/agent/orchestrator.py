import asyncio
from copy import deepcopy
import inspect
import json
import logging
import re
from datetime import date, timedelta
from pathlib import Path
from .llm_client import LLMClient
from .query_parser import QueryParser
from .intent_router import IntentRouter
from .schemas import AgentResponse, SearchFilters, SearchHotelsArgs, SearchTransportArgs, WeatherArgs
from .state_manager import StateManager
from .response_builder import make_response
from .tools.factory import build_registry
from .tools.executor import ToolExecutor
from .tools.search_hotels import search_hotels
from .tools.search_transport import search_transport
from .trip_assembly import assemble_trip
from ..catalog.normalize import normalize_city

logger = logging.getLogger(__name__)
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.md").read_text(encoding="utf-8")
COASTAL_CITIES = {"Сочи", "Новороссийск", "Калининград", "Евпатория", "Севастополь"}
CRIMEA_CITIES = {"Евпатория", "Севастополь"}


class AgentOrchestrator:
    def __init__(self, catalog, llm: LLMClient | None = None, max_tool_calls: int = 6):
        self.catalog = catalog
        self.llm = llm or LLMClient()
        self.parser = QueryParser(self.llm)
        self.router = IntentRouter()
        self.max_tool_calls = max_tool_calls

    async def handle_message(self, session_id: str, message: str, state: dict) -> AgentResponse:
        current = deepcopy(state or {})
        had_selected_hotel = bool(current.get("selected_hotel"))
        try:
            patch = await self.parser.parse(message, current)
            current = StateManager.update(current, patch)
            intent = self.router.detect(message, patch, current)
            if had_selected_hotel and message.casefold().strip() in {"завтра", "послезавтра"}:
                intent = "trip_search"
            current["last_intent"] = intent
            current["stage"] = {
                "inspiration": "inspiration", "hotel_search": "selection",
                "trip_search": "selection", "details": "selection",
                "compare": "selection", "replan": "planning",
                "itinerary": "planning", "checkout": "checkout", "weather": "planning",
            }.get(intent, current.get("stage") or "inspiration")
        except ValueError as exc:
            logger.info("Не удалось разобрать поездку: %s", exc)
            text = message.casefold()
            if "мор" in text or "крым" in text:
                trip = dict(current.get("trip") or {})
                origin = re.search(r"\bиз\s+([а-яё-]+)", text)
                if origin:
                    trip["origin_city"] = normalize_city(origin.group(1))
                nights = re.search(r"\bна\s+(\d+)\s+(?:дн|сут)", text)
                if nights:
                    trip["nights"] = int(nights.group(1))
                if "ноябр" in text:
                    trip["travel_month"] = 11
                budget = re.search(r"\bдо\s+(\d+)\s*тысяч", text)
                if budget:
                    trip["max_total_budget"] = int(budget.group(1)) * 1000
                current["trip"] = trip
                current["last_intent"] = "inspiration"
                return await self._inspiration(current, message)
            return make_response("clarification", "Не удалось разобрать условия поездки. Уточните, что нужно изменить.", current, message)
        except Exception:
            logger.exception("Ошибка парсинга session=%s", session_id)
            return make_response("error", "Модель недоступна или не смогла обработать запрос.", current, message)

        if intent == "inspiration":
            return await self._inspiration(current, message)
        if intent == "weather":
            return await self._weather(current, message)
        if intent == "checkout":
            if current.get("cart"):
                return make_response("results", "Корзина собрана для демонстрации. Проверьте состав и явно подтвердите демо-бронирование на сайте.",
                                     current, message, warnings=current.get("warnings") or [])
            return make_response("clarification", "Оформление пока не подключено. Позже мы покажем корзину и запросим ваше явное подтверждение демо-бронирования.", current, message)
        if intent == "itinerary":
            assembled = assemble_trip(current)
            if assembled.get("itinerary"):
                return make_response("results", "Показал выбранные варианты в маршруте.",
                                     assembled, message, warnings=assembled.get("warnings") or [])
            return make_response("clarification", "Чтобы собрать маршрут, выберите дорогу и отель.", current, message)
        if intent == "trip_search":
            missing = StateManager.missing_fields(current, intent)
            if missing:
                field = missing[0]
                question = "Из какого города вы отправляетесь?" if field == "город отправления" else "В какой город направляетесь?"
                return make_response("clarification", question, current, message)
        if intent == "replan":
            return make_response("clarification", "Изменения сохранены. Прежний маршрут и корзина помечены устаревшими; транспорт и проживание нужно перепроверить перед новой рекомендацией.", current, message)
        if intent == "details":
            return await self._hotel_details(current, message)
        if intent == "compare" and not current.get("last_hotel_ids"):
            return make_response("clarification", "Сначала выберите отели для сравнения — пока в диалоге нет сохранённых вариантов.", current, message)
        if intent == "hotel_search":
            missing = StateManager.missing_fields(current, intent)
            if missing:
                first = missing[0]
                prompts = {
                    "город": "В каком городе искать отель?",
                    "даты заезда и выезда": "На какие даты планируете проживание? Можно указать примерный период.",
                    "количество гостей": "Сколько человек будет проживать в отеле?",
                }
                return make_response("clarification", prompts.get(first, "Уточните: " + first), current, message)

        if intent == "chat":
            return await self._chat(current, message)
        return await self._tool_loop(current, message, intent, session_id)

    async def _weather(self, state: dict, message: str) -> AgentResponse:
        trip = state.get("trip") or {}
        city_or_id = trip.get("destination_id") or trip.get("city")
        if not city_or_id:
            return make_response("clarification", "Для какого города узнать погоду?", state, message)
        match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", message)
        target_date = match.group(0) if match else trip.get("check_in")
        text = message.casefold()
        if "завтра" in text:
            target_date = (date.today() + timedelta(days=1)).isoformat()
        elif "сегодня" in text:
            target_date = date.today().isoformat()
        month = None if target_date else trip.get("travel_month")
        if not isinstance(month, int) or not 1 <= month <= 12:
            month = None
        result = await ToolExecutor(build_registry(self.catalog, state)).execute(
            "get_weather", WeatherArgs(destination_id=trip.get("destination_id"),
                                        city=trip.get("city"), target_date=target_date,
                                        month=month).model_dump(exclude_none=True))
        if not result.get("ok"):
            return make_response("error", "Не удалось проверить погоду. Попробуйте позднее.", state, message)
        data = result.get("data") or {}
        if data.get("outcome") == "unavailable":
            return make_response("no_results", data["message"], state, message)
        if data.get("outcome") != "results":
            return make_response("clarification", data.get("message", "Уточните город и дату."), state, message)
        weather = data["weather"]
        city = data["city"]
        source_name = (weather.get("source") or {}).get("name") or "погодный источник"
        if weather["type"] == "exact_forecast":
            forecast = weather["forecast"]
            reply = (f"Город {city}. Прогноз на {weather['target_date']}: "
                     f"от {forecast['temp_min_c']} до {forecast['temp_max_c']} °C, "
                     f"осадки {forecast['precipitation_mm']} мм. "
                     f"Источник: {source_name}.")
        else:
            period = (f"месяц {weather['target_month']}" if weather.get("target_month")
                      else weather.get("target_date", "этот период"))
            reply = (f"Город {city}. На {period} историческая средняя температура — "
                     f"{weather['expected_temp_c']} °C. Это климатическая справка, "
                     "не прогноз погоды на конкретный день. "
                     f"Источник: {source_name}.")
        return make_response("results", reply, state, message, weather=weather)

    async def _inspiration(self, state: dict, message: str) -> AgentResponse:
        provider = getattr(self.catalog, "suggest_destinations", None)
        if not callable(provider):

            origin = state["trip"].get("origin_city")
            question = ("Какие условия важнее — климат, дорога или бюджет?" if origin else
                        "Из какого города вы хотели бы отправиться?")
            return make_response("clarification", "Для проверяемых рекомендаций пока не подключён источник направлений. " + question,
                                 state, message)
        params = {k: state["trip"].get(k) for k in (
            "origin_city", "travel_month", "travel_year", "flexible_dates",
            "nights", "max_total_budget", "currency", "preferences", "transport_mode"
        )}
        try:
            raw = provider(params)
            raw = await asyncio.wait_for(raw, timeout=30) if inspect.isawaitable(raw) else raw
            destinations = raw.get("destinations", []) if isinstance(raw, dict) else raw
            if not isinstance(destinations, list):
                raise ValueError("Неверный ответ источника направлений")
            destinations = [d for d in destinations if isinstance(d, dict) and d.get("name") and d.get("source")]
            text = message.casefold()
            if "крым" in text:
                destinations = [d for d in destinations if d.get("name") in CRIMEA_CITIES]
            elif "мор" in text:
                destinations = [d for d in destinations if d.get("name") in COASTAL_CITIES]
            destinations = destinations[:5]
        except Exception:
            logger.exception("Ошибка источника направлений")
            return make_response("error", "Источник направлений сейчас недоступен.", state, message)
        if not destinations:
            return make_response("no_results", "Пока не нашёл направлений по этим условиям.", state, message)
        state["last_destination_ids"] = [str(d.get("destination_id", d["name"])) for d in destinations]
        names = ", ".join(str(d["name"]) for d in destinations)
        return make_response("results", f"Вот направления из подключённого каталога: {names}. Уточним критерии и выберем подходящее.",
                             state, message, destinations=destinations)

    async def _hotel_details(self, state: dict, message: str) -> AgentResponse:
        number = self.router.referenced_hotel_number(message)
        ids = state.get("last_hotel_ids", [])
        if number is None or number < 1 or number > len(ids):
            return make_response("clarification", "Уточните, какой из ранее найденных отелей показать (например, «первый отель»).", state, message)

        executor = ToolExecutor(build_registry(self.catalog, state))
        result = await executor.execute("get_hotel_details", {"hotel_id": str(ids[number - 1])})
        if not result.get("ok"):
            return make_response("error", "Не удалось получить сведения об отеле.", state, message)
        hotel = result["data"].get("hotel")
        if not isinstance(hotel, dict):
            return make_response("no_results", "В каталоге не нашлось подробной информации об этом отеле.", state, message)

        parts = [str(hotel.get("name") or "Выбранный отель")]
        if hotel.get("city"):
            parts.append("город: " + str(hotel["city"]))
        if hotel.get("rating") is not None:
            parts.append("рейтинг: " + str(hotel["rating"]))
        return make_response("results", "; ".join(parts) + ". Остальные характеристики указаны в карточке.",
                             state, message, hotels=[hotel])

    async def _chat(self, state: dict, message: str) -> AgentResponse:
        messages = [{"role": "system", "content": SYSTEM_PROMPT + "\nНе придумывай факты о ценах, рейсах и отелях."}]
        messages += state.get("history", [])[-10:]
        messages.append({"role": "user", "content": message})
        try:
            response = await self.llm.chat(messages)
            reply = (response.message.content or "").strip()
            if reply:
                return make_response("clarification", reply, state, message)
        except Exception:
            logger.exception("Ошибка ответа LLM")
        return make_response("clarification", "Опишите, какую поездку хотите спланировать.", state, message)

    async def _tool_loop(self, state: dict, message: str, intent: str, session_id: str) -> AgentResponse:
        registry = build_registry(self.catalog, state)
        executor = ToolExecutor(registry)
        msgs = [{"role": "system", "content": SYSTEM_PROMPT + "\nТЕКУЩЕЕ СОСТОЯНИЕ: " + json.dumps(state.get("trip", {}), ensure_ascii=False)}]
        msgs += state.get("history", [])[-10:]
        msgs.append({"role": "user", "content": message})
        hotels: list[dict] = []
        transport_options: list[dict] = []
        warnings: list[str] = []
        any_success = False
        transport_issue: tuple[str, str] | None = None
        tool_count = 0
        answer = ""
        try:

            for _ in range(self.max_tool_calls + 1):
                response = await self.llm.chat(msgs, tools=registry.ollama_schemas())
                assistant = response.message
                calls = assistant.tool_calls or []
                if not calls:
                    answer = (assistant.content or "").strip()
                    break
                msgs.append(assistant.model_dump(exclude_none=True))
                for call in calls:
                    if tool_count >= self.max_tool_calls:
                        break
                    tool_count += 1
                    name = call.function.name
                    arguments = call.function.arguments
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except json.JSONDecodeError:
                            arguments = {}
                    if not isinstance(arguments, dict):
                        arguments = {}
                    executed = await executor.execute(name, arguments)
                    if name == "search_transport":
                        if not executed.get("ok"):
                            timed_out = executed.get("error") == "timeout"
                            transport_issue = (
                                "error",
                                "Поиск поездов не завершился: превышено время ожидания. Попробуйте ещё раз позднее."
                                if timed_out else
                                "Не удалось выполнить поиск поездов. Попробуйте ещё раз позднее.",
                            )
                        else:
                            transport_data = executed.get("data", {})
                            outcome = transport_data.get("outcome")
                            if outcome in {"clarification", "unavailable"}:
                                transport_issue = (outcome, transport_data.get("message", ""))
                    if executed.get("ok"):
                        any_success = True
                        if name == "search_hotels":
                            data = executed.get("data", {})
                            hotels = data.get("hotels", [])
                            warnings.extend(data.get("warnings", []))
                        elif name == "search_transport":
                            data = executed.get("data", {})
                            transport_options = data.get("transport_options", [])
                            warnings.extend(data.get("warnings", []))
                    msgs.append({"role": "tool", "tool_name": name,
                                 "content": json.dumps(executed, ensure_ascii=False, default=str)})
                if tool_count >= self.max_tool_calls:

                    response = await self.llm.chat(msgs)
                    answer = (response.message.content or "").strip()
                    break


            if intent == "hotel_search" and not hotels:
                trip = state["trip"]
                allowed = set(SearchFilters.model_fields)
                args = SearchHotelsArgs(
                    filters=SearchFilters.model_validate({k: v for k, v in trip.items() if k in allowed}),
                    preferences=trip.get("preferences") or [],
                )
                hotels = (await search_hotels(args, self.catalog, state))["hotels"]
                any_success = True

            trip = state.get("trip") or {}
            if (intent == "trip_search" and not transport_options and not trip.get("transport_mode")
                    and trip.get("origin_city") and trip.get("city") and trip.get("check_in")):
                for mode in ("plane", "bus"):
                    fallback = await search_transport(
                        SearchTransportArgs(type=mode, from_city=trip["origin_city"],
                                            to_city=trip["city"], date_from=trip["check_in"]),
                        self.catalog, state,
                    )
                    if fallback.get("outcome") == "results":
                        transport_options = fallback["transport_options"]
                        warnings.extend(fallback.get("warnings") or [])
                        transport_issue = None
                        break

            if transport_issue and (intent == "trip_search" or not hotels):
                issue_status, issue_message = transport_issue
                status = "clarification" if issue_status == "clarification" else "error"
                return make_response(status, issue_message, state, message)

            if transport_options:
                state["last_transport_ids"] = [str(item.get("transport_id")) for item in transport_options if item.get("transport_id")]
                state["last_transport_options"] = transport_options
                if all(item.get("record_kind") == "route_price_estimate" for item in transport_options):
                    reply = "Обновил результаты поиска."
                elif any(item.get("record_kind") == "live_offer" for item in transport_options):
                    reply = answer or f"В поиске Туту найдено {len(transport_options)} вариантов транспорта."
                else:
                    reply = answer or f"В каталоге найдено {len(transport_options)} вариантов транспорта."
                return make_response("results", reply, state, message, transport_options=transport_options,
                                     warnings=list(dict.fromkeys(warnings)))
            if hotels:
                state["last_hotel_ids"] = [str(h["hotel_id"]) for h in hotels]
                state["last_hotel_offers"] = hotels
                if all(h.get("price_estimate") and h.get("total_price") is None for h in hotels):
                    reply = f"В каталоге найдено {len(hotels)} объектов размещения."
                elif any(h.get("record_kind") == "live_offer" for h in hotels):
                    reply = answer or f"В поиске Туту найдено {len(hotels)} вариантов размещения на выбранные даты."
                else:
                    reply = answer or f"В каталоге найдено {len(hotels)} объектов размещения."
                if state.get("trip", {}).get("max_total_price") and any(h.get("total_price") is None for h in hotels):
                    warnings.append("У части вариантов цена не указана, поэтому соответствие бюджету подтвердить нельзя.")
                if any((h.get("availability") or {}).get("status") != "confirmed" for h in hotels):
                    warnings.append("Каталог содержит справочные данные; наличие номеров на даты не подтверждено.")
                return make_response("results", reply, state, message, hotels, warnings=list(dict.fromkeys(warnings)))
            if intent == "hotel_search":
                if state.get("trip", {}).get("required_amenities"):
                    return make_response("no_results", "Не нашёл отелей с указанными удобствами.", state, message)
                return make_response("no_results", "В подключённом каталоге подходящих отелей пока не найдено.", state, message)
            if intent == "trip_search":
                return make_response("no_results", "По заданным условиям в транспортном каталоге вариантов не найдено.", state, message,
                                     warnings=list(dict.fromkeys(warnings)))
            if any_success and answer:
                return make_response("results", answer, state, message)
            if answer:
                return make_response("clarification", answer, state, message)
            return make_response("clarification", "Не хватает данных для уверенного ответа. Уточните запрос.", state, message)
        except Exception:
            logger.exception("Ошибка агента session=%s", session_id)
            return make_response("error", "Не удалось завершить обработку запроса. Попробуйте повторить.", state, message)
