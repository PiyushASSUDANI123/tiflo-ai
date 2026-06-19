import threading
import time
from collections import Counter, deque
from statistics import mean
from typing import Optional


class TTLCache:
    def __init__(self, name: str, default_ttl: int = 300, max_items: int = 256):
        self.name = name
        self.default_ttl = default_ttl
        self.max_items = max_items
        self._data = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.sets = 0

    def _purge_expired(self, now: Optional[float] = None):
        now = now or time.time()
        expired = [key for key, (_, expires_at) in self._data.items() if expires_at <= now]
        for key in expired:
            self._data.pop(key, None)

    def get(self, key):
        now = time.time()
        with self._lock:
            self._purge_expired(now)
            item = self._data.get(key)
            if not item:
                self.misses += 1
                return None
            value, expires_at = item
            if expires_at <= now:
                self._data.pop(key, None)
                self.misses += 1
                return None
            self.hits += 1
            return value

    def set(self, key, value, ttl: Optional[int] = None):
        now = time.time()
        expires_at = now + (ttl if ttl is not None else self.default_ttl)
        with self._lock:
            self._purge_expired(now)
            if len(self._data) >= self.max_items:
                oldest_key = min(self._data, key=lambda item_key: self._data[item_key][1])
                self._data.pop(oldest_key, None)
            self._data[key] = (value, expires_at)
            self.sets += 1

    def snapshot(self) -> dict:
        now = time.time()
        with self._lock:
            self._purge_expired(now)
            return {
                "name": self.name,
                "size": len(self._data),
                "hits": self.hits,
                "misses": self.misses,
                "sets": self.sets,
                "default_ttl": self.default_ttl,
                "max_items": self.max_items,
            }


class RuntimeMetrics:
    def __init__(self):
        self.started_at = time.time()
        self._lock = threading.Lock()
        self.active_requests = 0
        self.total_requests = 0
        self.total_errors = 0
        self.endpoint_counts = Counter()
        self.intent_counts = Counter()
        self.mode_counts = Counter()
        self.tool_counts = Counter()
        self.provider_counts = Counter()
        self.cache_counts = Counter()
        self.latencies_ms = {}

    def start_request(self, endpoint: str, mode: str = "") -> float:
        started = time.time()
        with self._lock:
            self.active_requests += 1
            self.total_requests += 1
            self.endpoint_counts[endpoint] += 1
            if mode:
                self.mode_counts[mode] += 1
        return started

    def finish_request(self, endpoint: str, started_at: float, ok: bool = True):
        elapsed_ms = (time.time() - started_at) * 1000
        with self._lock:
            self.active_requests = max(0, self.active_requests - 1)
            if not ok:
                self.total_errors += 1
            bucket = self.latencies_ms.setdefault(endpoint, deque(maxlen=200))
            bucket.append(round(elapsed_ms, 2))
        return round(elapsed_ms, 2)

    def record_intent(self, intent: str):
        if not intent:
            return
        with self._lock:
            self.intent_counts[intent] += 1

    def record_tool(self, tool_name: str):
        if not tool_name:
            return
        with self._lock:
            self.tool_counts[tool_name] += 1

    def record_provider(self, provider_name: str):
        if not provider_name:
            return
        with self._lock:
            self.provider_counts[provider_name] += 1

    def record_cache_hit(self, cache_name: str):
        with self._lock:
            self.cache_counts[f"{cache_name}:hit"] += 1

    def record_cache_miss(self, cache_name: str):
        with self._lock:
            self.cache_counts[f"{cache_name}:miss"] += 1

    def snapshot(self) -> dict:
        with self._lock:
            latency_snapshot = {
                endpoint: {
                    "count": len(samples),
                    "avg_ms": round(mean(samples), 2) if samples else 0,
                    "max_ms": round(max(samples), 2) if samples else 0,
                }
                for endpoint, samples in self.latencies_ms.items()
            }
            return {
                "uptime_seconds": int(time.time() - self.started_at),
                "active_requests": self.active_requests,
                "total_requests": self.total_requests,
                "total_errors": self.total_errors,
                "endpoint_counts": dict(self.endpoint_counts),
                "intent_counts": dict(self.intent_counts),
                "mode_counts": dict(self.mode_counts),
                "tool_counts": dict(self.tool_counts),
                "provider_counts": dict(self.provider_counts),
                "cache_counts": dict(self.cache_counts),
                "latencies_ms": latency_snapshot,
            }


runtime_metrics = RuntimeMetrics()
router_cache = TTLCache("router", default_ttl=180, max_items=512)
summary_cache = TTLCache("summary", default_ttl=1800, max_items=128)
search_cache = TTLCache("search", default_ttl=120, max_items=128)
followup_cache = TTLCache("followups", default_ttl=600, max_items=128)
