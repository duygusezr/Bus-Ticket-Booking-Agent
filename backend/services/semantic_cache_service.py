"""
Semantic cache — disabled by default (ENABLED = False).
SentenceTransformer is NOT loaded when disabled to avoid wasting ~200MB RAM.
"""
import numpy as np
import re
import time
import logging
import warnings
import os
from typing import Optional, Dict, Any, List

logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*unauthenticated.*")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

_ENABLED = False  # Flip to True to activate


class SemanticCache:
    ENABLED: bool = _ENABLED

    def __init__(self) -> None:
        self._cache: List[Dict[str, Any]] = []
        self.threshold: float = 0.90
        self.max_items: int = 500
        self._model = None

        if self.ENABLED:
            self._load_model()

    def _load_model(self) -> None:
        import sys, io
        from sentence_transformers import SentenceTransformer
        _old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        finally:
            sys.stdout = _old_stdout
        print("[SEMANTIC CACHE] Model loaded.")

    def _clean(self, query: str) -> str:
        return re.sub(r"\[SİSTEM BİLGİSİ.*?\]", "", query).strip()

    def search(self, query: str) -> Optional[Dict[str, Any]]:
        if not self.ENABLED or self._model is None:
            return None

        clean = self._clean(query)
        if len(clean) < 5 or not self._cache:
            return None

        # Bypass for digit-heavy inputs (TC, seat, phone)
        if sum(c.isdigit() for c in clean) > len(clean) / 2:
            return None

        t0 = time.perf_counter()
        vec = self._model.encode(clean, convert_to_numpy=True)

        best_score, best_data = -1.0, None
        for item in self._cache:
            score = float(np.dot(vec, item["vector"]) / (np.linalg.norm(vec) * np.linalg.norm(item["vector"]) + 1e-9))
            if score > best_score:
                best_score, best_data = score, item["data"]

        elapsed = time.perf_counter() - t0
        if best_score >= self.threshold:
            print(f"[SEMANTIC CACHE] HIT score={best_score:.3f} t={elapsed:.3f}s")
            return best_data

        print(f"[SEMANTIC CACHE] MISS score={best_score:.3f} t={elapsed:.3f}s")
        return None

    def add(self, query: str, text: str, audio: str, emotion: str) -> None:
        if not self.ENABLED or self._model is None:
            return

        clean = self._clean(query)
        if self.search(clean) is not None:
            return

        if len(self._cache) >= self.max_items:
            self._cache.pop(0)

        vec = self._model.encode(clean, convert_to_numpy=True)
        self._cache.append({
            "vector": vec,
            "data": {"text": text, "audio": audio, "emotion": emotion, "query": query},
        })


semantic_cache = SemanticCache()
