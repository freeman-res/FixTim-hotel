import os
from typing import Any


class Embedder:
    def __init__(self, model_name: str | None = None, host: str | None = None,
                 batch_size: int = 32, client: Any = None):
        if batch_size < 1:
            raise ValueError("batch_size должен быть положительным")
        if client is None:
            from ollama import Client
            client = Client(host=host or os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"), timeout=120)
        self.client = client
        self.model_name = model_name or os.getenv("OLLAMA_EMBED_MODEL", "bge-m3")
        self.batch_size = batch_size
        self.dim: int | None = None

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        output: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            chunk = texts[start:start + self.batch_size]
            if any(not isinstance(x, str) or not x.strip() for x in chunk):
                raise ValueError("Для эмбеддингов нужны непустые строки")
            response = self.client.embed(model=self.model_name, input=chunk)
            vectors = response.embeddings if hasattr(response, "embeddings") else response["embeddings"]
            if len(vectors) != len(chunk):
                raise RuntimeError("Неполное количество эмбеддингов в ответе Ollama")
            for vector in vectors:
                if self.dim is None:
                    self.dim = len(vector)
                if len(vector) != self.dim:
                    raise RuntimeError("Несовпадение размерности эмбеддингов")
                output.append(list(vector))
        return output

    def encode_query(self, query: str) -> list[float]:
        return self.encode([query])[0]
