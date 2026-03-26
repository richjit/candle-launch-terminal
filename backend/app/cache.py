import time
from threading import Lock


class MemoryCache:
    def __init__(self):
        self._store: dict[str, tuple[float, object]] = {}
        self._lock = Lock()

    def get(self, key: str):
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: object, ttl: int):
        with self._lock:
            self._store[key] = (time.time() + ttl, value)

    def delete(self, key: str):
        with self._lock:
            self._store.pop(key, None)


class RateLimiter:
    def __init__(self, max_calls: int, period: float):
        self._max_calls = max_calls
        self._period = period
        self._calls: dict[str, list[float]] = {}
        self._lock = Lock()

    def allow(self, source: str) -> bool:
        now = time.time()
        with self._lock:
            if source not in self._calls:
                self._calls[source] = []
            # Remove expired timestamps
            self._calls[source] = [t for t in self._calls[source] if now - t < self._period]
            if len(self._calls[source]) >= self._max_calls:
                return False
            self._calls[source].append(now)
            return True
