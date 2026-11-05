from __future__ import annotations
import json
import logging
from pathlib import Path
import numpy as np
log = logging.getLogger(__name__)
try:
    import faiss
    _HAS_FAISS = True
except ImportError:
    _HAS_FAISS = False
def _l2_normalize(v: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (v / norms).astype("float32")
class VectorStore:
    def __init__(self, index_dir: Path):
        self.index_dir = Path(index_dir)
        self.vectors: np.ndarray | None = None
        self.metadata: list[dict] = []
        self.manifest: dict = {}
        self._faiss_index = None
        self._backend = "empty"



    def save(self, vectors: np.ndarray, metadata: list[dict],
             manifest: dict) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        vectors = _l2_normalize(np.asarray(vectors, dtype="float32"))

        if _HAS_FAISS:
            import faiss
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            faiss.write_index(index, str(self.index_dir / "vectors.faiss"))
            self._backend = "faiss"
        else:
            np.save(self.index_dir / "vectors.npy", vectors)
            self._backend = "numpy"

        (self.index_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False), encoding="utf-8"
        )
        (self.index_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log.info("VectorStore.save: backend=%s, chunks=%d, dim=%d",
                 self._backend, len(metadata), vectors.shape[1])



    def load(self) -> bool:
        meta_path     = self.index_dir / "metadata.json"
        manifest_path = self.index_dir / "manifest.json"
        if not (meta_path.exists() and manifest_path.exists()):
            return False
        self.metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        faiss_path = self.index_dir / "vectors.faiss"
        npy_path   = self.index_dir / "vectors.npy"
        if _HAS_FAISS and faiss_path.exists():
            import faiss
            self._faiss_index = faiss.read_index(str(faiss_path))
            self._backend = "faiss"
        elif npy_path.exists():
            self.vectors = np.load(npy_path)
            self._backend = "numpy"
        else:
            return False
        log.info("VectorStore.load: backend=%s, chunks=%d",
                 self._backend, len(self.metadata))
        return True

    def search(self, query_vector: np.ndarray, top_k: int,
               allowed_hotel_ids: set[str] | None = None) -> list[dict]:
        """ Возвращает до top_k чанков, отсортированных по score.
        allowed_hotel_ids — ЖЁСТКИЙ фильтр. ТЗ п.5 требует
        "не возвращать отзывы другого отеля" — гарантируем здесь,
        независимо от того, что попросил №2."""
        if not self.metadata or top_k <= 0:
            return []
        q = _l2_normalize(np.asarray(query_vector, dtype="float32").reshape(1, -1))
        if allowed_hotel_ids is not None:


            candidates = [i for i, item in enumerate(self.metadata)
                          if item.get("hotel_id") in allowed_hotel_ids]
            if not candidates:
                return []
            scores = np.empty(len(candidates), dtype="float32")
            for start in range(0, len(candidates), 1024):
                batch = candidates[start:start + 1024]
                if self._backend == "faiss" and self._faiss_index is not None:
                    vectors = self._faiss_index.reconstruct_batch(
                        np.asarray(batch, dtype="int64")
                    )
                elif self._backend == "numpy" and self.vectors is not None:
                    vectors = self.vectors[batch]
                else:
                    return []
                scores[start:start + len(batch)] = np.asarray(vectors) @ q[0]
            return [dict(self.metadata[candidates[pos]], score=float(scores[pos]))
                    for pos in np.argsort(-scores, kind="stable")[:top_k]]

        fetch_n = min(top_k, len(self.metadata))
        if self._backend == "faiss" and self._faiss_index is not None:
            scores, ids = self._faiss_index.search(q, fetch_n)
            scores, ids = scores[0], ids[0]
        elif self._backend == "numpy" and self.vectors is not None:
            sims = (self.vectors @ q.T).ravel()
            top_idx = np.argsort(-sims)[:fetch_n]
            ids, scores = top_idx, sims[top_idx]
        else:
            return []
        out: list[dict] = []
        for i, score in zip(ids, scores):
            if i < 0 or i >= len(self.metadata):
                continue
            item = dict(self.metadata[i])
            item["score"] = float(score)
            out.append(item)
            if len(out) >= top_k:
                break
        return out
