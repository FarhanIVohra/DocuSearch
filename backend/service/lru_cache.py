from typing import Any, Dict, Optional, Tuple


class _Node:
    __slots__ = ("key", "value", "prev", "next")
    def __init__(self, key: str, value: Any):
        self.key = key
        self.value = value
        self.prev: Optional["_Node"] = None
        self.next: Optional["_Node"] = None


class LRUCache:
    """
    O(1) get/put LRU cache with hit/miss stats.
    Keys are normalized query strings; values are search results (list of tuples).
    """
    def __init__(self, capacity: int = 256):
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self.capacity = capacity
        self.map: Dict[str, _Node] = {}
        self.head = _Node("", None)
        self.tail = _Node("", None)
        self.head.next = self.tail
        self.tail.prev = self.head
        self.hits = 0
        self.misses = 0

    def _remove(self, node: _Node) -> None:
        prev, nxt = node.prev, node.next
        if prev is not None:
            prev.next = nxt
        if nxt is not None:
            nxt.prev = prev
        node.prev = node.next = None

    def _insert_front(self, node: _Node) -> None:
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node  # type: ignore
        self.head.next = node

    def _evict_lru(self) -> None:
        lru = self.tail.prev
        if lru is None or lru is self.head:
            return
        self._remove(lru)
        self.map.pop(lru.key, None)

    def get(self, key: str) -> Optional[Any]:
        node = self.map.get(key)
        if not node:
            self.misses += 1
            return None
        self._remove(node)
        self._insert_front(node)
        self.hits += 1
        return node.value

    def put(self, key: str, value: Any) -> None:
        node = self.map.get(key)
        if node:
            node.value = value
            self._remove(node)
            self._insert_front(node)
            return
        node = _Node(key, value)
        self.map[key] = node
        self._insert_front(node)
        if len(self.map) > self.capacity:
            self._evict_lru()

    def stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        hit_ratio = (self.hits / total) if total else 0.0
        return {
            "capacity": self.capacity,
            "size": len(self.map),
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio": hit_ratio,
        }
