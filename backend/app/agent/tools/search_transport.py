"""Transport search through the CatalogGateway contract."""

from ..schemas import SearchTransportArgs
from rzd_api import RzdAmbiguousStationError, RzdError, RzdStationNotFoundError, RzdValidationError
from ...catalog.transport.rzd_provider import RzdPartialSearchError


async def search_transport(args: SearchTransportArgs, catalog, state: dict) -> dict:
    trip = state.get("trip", {})
    filters = args.model_dump(exclude_none=True, exclude={"limit"})
    if not filters.get("from_city"):
        filters["from_city"] = trip.get("origin_city")
    if not filters.get("to_city"):
        filters["to_city"] = trip.get("city")
    if not filters.get("type"):
        filters["type"] = trip.get("transport_mode")
    if not filters.get("date_from"):
        filters["date_from"] = trip.get("check_in")
    if not filters.get("date_to"):
        filters["date_to"] = trip.get("check_in")
    if trip.get("adults") is not None:
        filters["adults"] = trip["adults"]
    filters = {key: value for key, value in filters.items() if value is not None}
    if filters.get("type") == "any":
        filters.pop("type")
    elif filters.get("type") == "flight":
        filters["type"] = "plane"
    if filters.get("type") == "train" and not filters.get("date_from"):
        return {
            "outcome": "clarification",
            "message": "Для поиска поезда нужна точная дата отправления. На какой день искать?",
            "transport_options": [], "count": 0, "filters": filters, "warnings": [],
        }
    if filters.get("type") == "plane" and not filters.get("date_from"):
        return {
            "outcome": "clarification",
            "message": "Для поиска авиабилета нужна дата вылета. На какой день искать?",
            "transport_options": [], "count": 0, "filters": filters, "warnings": [],
        }
    if (filters.get("type") == "train" and filters.get("date_to")
            and filters["date_to"] != filters.get("date_from")):
        return {
            "outcome": "clarification",
            "message": "РЖД проверяет поезда на одну дату за запрос. Укажите точный день отправления.",
            "transport_options": [], "count": 0, "filters": filters, "warnings": [],
        }
    try:
        options = await catalog.find_transport(filters)
    except RzdAmbiguousStationError as exc:
        candidates = ", ".join(item.name for item in exc.candidates[:5])
        return {
            "outcome": "clarification",
            "message": f"Уточните станцию отправления или прибытия. Подходящие варианты: {candidates}.",
            "transport_options": [], "count": 0, "filters": filters, "warnings": [],
        }
    except RzdStationNotFoundError:
        return {
            "outcome": "clarification",
            "message": "РЖД не распознало один из городов или вокзалов. Уточните города отправления и прибытия.",
            "transport_options": [], "count": 0, "filters": filters, "warnings": [],
        }
    except RzdPartialSearchError:
        return {
            "outcome": "unavailable",
            "message": "РЖД вернуло неполный ответ без списка поездов; отсутствие рейсов подтвердить нельзя.",
            "transport_options": [], "count": 0, "filters": filters, "warnings": [],
        }
    except RzdValidationError:
        return {
            "outcome": "clarification",
            "message": "РЖД отклонило параметры поиска. Проверьте города и дату отправления.",
            "transport_options": [], "count": 0, "filters": filters, "warnings": [],
        }
    except (RzdError, ValueError):
        return {
            "outcome": "unavailable", "message": "Сервис расписания РЖД сейчас недоступен или вернул ошибку.",
            "transport_options": [], "count": 0, "filters": filters, "warnings": [],
        }
    options = options if isinstance(options, list) else []
    limit = args.limit
    warnings = []
    if (filters.get("type") == "plane" and filters.get("date_to")
            and filters["date_to"] != filters.get("date_from")):
        warnings.append("Поиск авиабилетов выполнен на начальную дату диапазона; остальные даты не проверялись.")
    if options and any(item.get("record_kind") == "route_price_estimate" for item in options):
        warnings.append("Цена перелёта — только оценка маршрута. Рейс, расписание и наличие билета не подтверждены.")
    elif options and any(item.get("record_kind") == "live_offer" for item in options):
        warnings.append("Цена получена из поиска Туту; проверьте итоговую стоимость и наличие билета перед покупкой.")
    elif options:
        warnings.append(
            "Данные транспорта основаны на датасетах; конкретная доступность и актуальность расписания требуют проверки у перевозчика."
        )
    if any((item.get("source") or {}).get("partial") for item in options):
        warnings.append("РЖД вернуло неполный ответ; список поездов может быть неполным.")
    if any(
        item.get("type") == "bus"
        and "route_level" in str((item.get("price") or {}).get("scope", ""))
        for item in options
    ):
        warnings.append("У части автобусов цена указана для маршрута, а не подтверждённого отправления.")
    return {
        "outcome": "results" if options else "no_results",
        "transport_options": options[:limit],
        "count": min(len(options), limit),
        "filters": filters,
        "warnings": warnings,
    }
