"""Интеграционная проверка зоны ответственности №2 на сервере с Ollama.

Запуск из корня проекта:
    python -m tests.agent.smoke_real_ollama

Никаких файлов/таблиц от №1/№3/№4 не создаёт: DemoCatalog живёт только в этом тесте.
Используются НАСТОЯЩИЕ модели Llama и BGE-M3, а отели демонстрационные.
"""
import asyncio
import json
import sys

from backend.app.agent.llm_client import LLMClient
from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.agent.schemas import TripPatch
from backend.app.agent.tools.executor import ToolExecutor
from backend.app.agent.tools.factory import build_registry
from backend.app.catalog.rag.embeddings import Embedder


class DemoCatalog:
    """Только тестовая замена поиска №3; не часть работающего каталога."""

    def __init__(self):
        self.calls = []
        self.hotels = [
            {
                "hotel_id": "demo-1", "offer_id": "offer-1", "name": "ДЕМО: Тихий берег",
                "city": "Сочи", "total_price": 24000, "currency": "RUB",
                "rating": 4.7, "amenities": ["pool", "wifi"], "semantic_score": 0.93,
            },
            {
                "hotel_id": "demo-2", "offer_id": "offer-2", "name": "ДЕМО: Городской отель",
                "city": "Сочи", "total_price": 28000, "currency": "RUB",
                "rating": 4.8, "amenities": ["wifi"], "semantic_score": 0.4,
            },
            {
                "hotel_id": "demo-3", "offer_id": "offer-3", "name": "ДЕМО: Дороже бюджета",
                "city": "Сочи", "total_price": 49000, "currency": "RUB",
                "rating": 5.0, "amenities": ["pool"], "semantic_score": 0.8,
            },
        ]

    async def find_offers(self, filters):
        self.calls.append(("find_offers", filters))

        return self.hotels

    async def get_hotel(self, hotel_id):
        self.calls.append(("get_hotel", hotel_id))
        return next((h for h in self.hotels if h["hotel_id"] == str(hotel_id)), None)

    async def get_hotels_by_ids(self, hotel_ids):
        self.calls.append(("get_hotels_by_ids", hotel_ids))
        return [h for h in self.hotels if h["hotel_id"] in hotel_ids]

    async def retrieve_reviews(self, query, hotel_ids, top_k=5):
        self.calls.append(("retrieve_reviews", query))
        return [{"hotel_id": "demo-1", "source": "demo-review-1", "text": "Ночью было тихо"}]


async def main():
    errors = []
    llm = LLMClient()
    catalog = DemoCatalog()

    print("\n[1/4] Проверка BGE-M3 через Python SDK")
    try:
        embedder = Embedder()
        vec = embedder.encode_query("Тихий отель с бассейном у моря")
        print(f"  размерность: {len(vec)}, первые 3 числа: {vec[:3]}")
        if len(vec) != 1024:
            errors.append("Неожиданная размерность BGE-M3")
    except Exception as exc:
        errors.append(f"BGE-M3: {type(exc).__name__}: {exc}")

    print("\n[2/4] Проверка Structured Outputs: QueryParser")
    try:

        agent = AgentOrchestrator(catalog=catalog, llm=llm)
        patch = await agent.parser.parse("Теперь обязательно нужен бассейн", {"trip": {"city": "Сочи"}})
        print("  TripPatch:", patch.model_dump_json(exclude_none=True, ensure_ascii=False))
        if "pool" not in (patch.required_amenities or []):
            errors.append("QueryParser не извлёк обязательный бассейн")
    except Exception as exc:
        errors.append(f"QueryParser: {type(exc).__name__}: {exc}")

    print("\n[3/4] Проверка настоящего Tool Calling Llama -> Python")
    state = {"trip": {"city": "Сочи", "max_total_price": 30000, "required_amenities": ["pool"], "currency": "RUB"}}
    registry = build_registry(catalog, state)
    try:
        response = await llm.chat(
            [
                {"role": "system", "content": "Для поиска гостиниц обязательно вызови инструмент search_hotels. Не выдумывай гостиницы."},
                {"role": "user", "content": "Найди в Сочи отели с бассейном до 30000 рублей. Вызови search_hotels."},
            ],
            tools=registry.ollama_schemas(),
        )
        calls = response.message.tool_calls or []
        print("  инструменты, выбранные моделью:", [call.function.name for call in calls])
        selected_search = [call for call in calls if call.function.name == "search_hotels"]
        if not selected_search:
            errors.append("Llama не выбрала search_hotels в тестовом Tool Calling")
            print("  текст модели:", str(response.message.content or "")[:400])
        else:
            raw_args = selected_search[0].function.arguments
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            executed = await ToolExecutor(registry).execute("search_hotels", args)
            print("  выполнение инструмента:", json.dumps(executed, ensure_ascii=False, default=str)[:700])
            if not executed.get("ok"):
                errors.append(f"ToolExecutor вернул ошибку: {executed}")
            elif [h["hotel_id"] for h in executed["data"]["hotels"]] != ["demo-1"]:
                errors.append("search_hotels не соблюдает обязательные фильтры")
    except Exception as exc:
        errors.append(f"Tool Calling: {type(exc).__name__}: {exc}")

    print("\n[4/4] Проверка полного AgentOrchestrator с реальной Llama")
    state = {"trip": {
        "city": "Сочи", "check_in": "2026-11-12", "check_out": "2026-11-15",
        "guests": 2, "max_total_price": 30000, "currency": "RUB",
    }}
    try:
        result = await AgentOrchestrator(catalog, llm=llm).handle_message(
            "demo-session", "Теперь обязательно бассейн", state
        )
        print("  status:", result.status)
        print("  reply:", result.reply[:500])
        print("  hotels:", [h.get("hotel_id") for h in result.hotels])
        if result.status != "results" or [h["hotel_id"] for h in result.hotels] != ["demo-1"]:
            errors.append("Полный цикл агента не вернул ожидаемый demo-1")
        if "pool" not in result.updated_state.get("trip", {}).get("required_amenities", []):
            errors.append("Оркестратор не сохранил требование pool")
    except Exception as exc:
        errors.append(f"Orchestrator: {type(exc).__name__}: {exc}")

    print("\n--- РЕЗУЛЬТАТ ---")
    if errors:
        for err in errors:
            print("FAIL:", err)
        print("Тест выявил ошибки/ограничения. Это НЕ означает, что весь агент готов.")
        return 1
    print("PASS: проверены Python-клиенты, схемы, настоящий Tool Calling и оркестратор.")
    print("ПРИМЕЧАНИЕ: каталог фиктивный, SQL/RAG/Backend не проверялись.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
