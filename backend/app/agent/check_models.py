"""Проверка Llama и BGE-M3 на сервере без каталога (python -m backend.app.agent.check_models)."""
import asyncio
from .llm_client import LLMClient
from backend.app.catalog.rag.embeddings import Embedder


async def main():
    llm = LLMClient()
    response = await llm.chat([{"role": "user", "content": "Одним предложением: что такое AI-агент для отелей?"}])
    print("LLM:", response.message.content)
    encoder = Embedder()
    vector = encoder.encode_query("Тихая гостиница недалеко от моря")
    print(f"BGE-M3: {len(vector)} чисел, пример: {vector[:3]}")


if __name__ == "__main__":
    asyncio.run(main())
