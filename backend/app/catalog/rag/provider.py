
from __future__ import annotations

import importlib
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Sequence

import numpy as np

log = logging.getLogger(__name__)


class EmbeddingsProvider(ABC):
    """Контракт: encode() возвращает np.ndarray shape=(len(texts), dim)."""
    dim: int
    model_name: str = "unknown"

    @abstractmethod
    def encode(self, texts: Sequence[str]) -> np.ndarray: ...


class UnavailableProvider(EmbeddingsProvider):
    """«Нет зависимости». encode() бросает, retrieve() ловит и возвращает []."""
    dim = 0
    model_name = "unavailable"

    def __init__(self, reason: str):
        self.reason = reason

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        raise RuntimeError(f"EmbeddingsProvider недоступен: {self.reason}")


class MemberTwoEmbedderAdapter(EmbeddingsProvider):
    """
    Оборачивает Embedder участника №2.

    Сглаживает:
        - list[list[float]] → np.ndarray(float32)
        - dim: None у №2 → лениво узнаём после первого encode
        - пустые строки (№2 бросает ValueError) → заменяем на " "
    """

    def __init__(self, embedder: Any):
        self._e = embedder
        self.dim = 0
        self.model_name = getattr(embedder, "model_name", "bge-m3") or "bge-m3"

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim or 0), dtype="float32")
        cleaned = [(t if isinstance(t, str) and t.strip() else " ") for t in texts]
        raw = self._e.encode(cleaned)
        arr = np.asarray(raw, dtype="float32")
        if arr.ndim != 2:
            raise RuntimeError(
                f"Адаптер №2: ожидался 2D-массив, получено shape={arr.shape}"
            )
        if arr.shape[0] != len(texts):
            raise RuntimeError(
                f"Адаптер №2: ожидалось {len(texts)} векторов, получено {arr.shape[0]}"
            )
        if self.dim == 0:
            self.dim = int(arr.shape[1])
        elif int(arr.shape[1]) != self.dim:
            raise RuntimeError(
                f"Адаптер №2: размерность изменилась с {self.dim} на {arr.shape[1]}"
            )
        return arr


_CANDIDATE_MODULES = (
    "backend.app.catalog.rag.embeddings_bge_m3",
    "backend.app.agent.rag.embeddings",
    "backend.app.agent.embeddings",
    "backend.app.rag.embeddings",
)


def _try_import_first() -> tuple[Any | None, str | None]:
    env_path = os.getenv("EMBEDDINGS_MODULE")
    candidates = (env_path,) if env_path else _CANDIDATE_MODULES
    last_exc: str | None = None
    for path in candidates:
        try:
            return importlib.import_module(path), None
        except ImportError as exc:
            last_exc = f"{path}: {exc}"
            log.debug("Кандидат %s не импортировался: %s", path, exc)
    return None, last_exc


def _wrap_embedder(obj: Any) -> EmbeddingsProvider:
    if isinstance(obj, EmbeddingsProvider):
        return obj
    if hasattr(obj, "encode"):
        return MemberTwoEmbedderAdapter(obj)
    return UnavailableProvider(
        f"Объект {type(obj).__name__} не имеет метода encode()"
    )


def make_provider() -> EmbeddingsProvider:
    mod, err = _try_import_first()
    if mod is None:
        log.warning("Модуль эмбеддингов №2 не найден (%s). RAG отключён.", err)
        return UnavailableProvider(f"no embeddings module: {err}")

    factory = getattr(mod, "make_provider", None)
    if callable(factory):
        try:
            provider = factory()
        except Exception as exc:
            log.error("%s.make_provider() упал: %s", mod.__name__, exc)
            return UnavailableProvider(f"make_provider() failed: {exc}")
        if isinstance(provider, EmbeddingsProvider):
            log.info("Embeddings: %s (dim=%s)",
                     provider.model_name, provider.dim)
            return provider
        return _wrap_embedder(provider)

    embedder_cls = getattr(mod, "Embedder", None)
    if embedder_cls is not None:
        try:
            embedder_obj = embedder_cls()
        except ImportError as exc:
            log.warning("Embedder №2 не создан (нет ollama?): %s", exc)
            return UnavailableProvider(f"Embedder init failed: {exc}")
        except Exception as exc:
            log.error("Embedder №2 упал при создании: %s", exc)
            return UnavailableProvider(f"Embedder init failed: {exc}")
        provider = _wrap_embedder(embedder_obj)
        log.info("Embeddings adapter №2: model=%s", provider.model_name)
        return provider

    log.warning("В модуле %s нет ни make_provider(), ни Embedder", mod.__name__)
    return UnavailableProvider(
        f"{mod.__name__} has neither make_provider() nor Embedder")
