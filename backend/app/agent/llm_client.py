"""Асинхронный Ollama-клиент. LLM может быть заменена через env."""
import os
from typing import Any


class LLMClient:
    def __init__(self, model: str | None = None, host: str | None = None, client: Any = None):
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        if client is None:
            from ollama import AsyncClient
            client = AsyncClient(host=host or os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"), timeout=300)
        self.client = client
        self.context_tokens = int(os.getenv("OLLAMA_NUM_CTX", "8192"))

    async def chat(self, messages: list[dict], tools: list[dict] | None = None, response_format: dict | None = None):
        kwargs = {
            "model": self.model,
            "messages": messages,
            "options": {"temperature": 0.15, "num_ctx": self.context_tokens},
        }
        if tools is not None:
            kwargs["tools"] = tools
        if response_format is not None:
            kwargs["format"] = response_format
        return await self.client.chat(**kwargs)
