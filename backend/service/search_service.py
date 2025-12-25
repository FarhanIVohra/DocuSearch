import time
from typing import Any, Dict, List, Tuple, Optional
from ..index.search import search as core_search
from ..index.preprocess import preprocess
from .lru_cache import LRUCache


class SearchService:
    """
    Thin service around core search adding:
    - query normalization
    - LRU caching (optional)
    - latency measurement
    - stats exposure
    """
    def __init__(self, index: Dict[str, Any], cache_capacity: int = 0) -> None:
        self.index = index
        self.cache: Optional[LRUCache] = LRUCache(cache_capacity) if cache_capacity > 0 else None
        self.total_queries = 0
        self.total_time_ms = 0.0

    def _normalize_key(self, query: str) -> str:
        toks = preprocess(query)
        return " ".join(toks)

    def search(self, query: str) -> Dict[str, Any]:
        start = time.perf_counter()
        self.total_queries += 1

        q = (query or "").strip()
        if not q:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.total_time_ms += elapsed_ms
            return {"results": [], "elapsed_ms": elapsed_ms, "cached": False}

        key = self._normalize_key(q)
        if not key:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.total_time_ms += elapsed_ms
            return {"results": [], "elapsed_ms": elapsed_ms, "cached": False}

        if self.cache is not None:
            cached = self.cache.get(key)
            if cached is not None:
                elapsed_ms = (time.perf_counter() - start) * 1000
                self.total_time_ms += elapsed_ms
                return {"results": cached, "elapsed_ms": elapsed_ms, "cached": True}

        results: List[Tuple[int, float]] = core_search(q, self.index)

        if self.cache is not None and results:
            self.cache.put(key, results)

        elapsed_ms = (time.perf_counter() - start) * 1000
        self.total_time_ms += elapsed_ms
        return {"results": results, "elapsed_ms": elapsed_ms, "cached": False}

    def stats(self) -> Dict[str, Any]:
        svc = {
            "total_queries": self.total_queries,
            "avg_latency_ms": (self.total_time_ms / self.total_queries) if self.total_queries else 0.0,
        }
        if self.cache is not None:
            svc["cache"] = self.cache.stats()
        else:
            svc["cache"] = {"enabled": False}
        return svc
