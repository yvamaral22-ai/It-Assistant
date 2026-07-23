import json
import time
from collections import defaultdict, deque
from threading import Lock

from app.config import resolve_data_path


class FileRateLimiter:
    """Small persistent sliding-window limiter for local/internal deployments."""

    def __init__(self, store_path: str, namespace: str, limit: int, window_seconds: int):
        self.store_path = resolve_data_path(store_path)
        self.namespace = namespace
        self.limit = limit
        self.window_seconds = window_seconds
        self._lock = Lock()

    def allowed(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            data = self._load()
            entries = self._recent(data, key, now)
            return len(entries) < self.limit

    def hit(self, key: str) -> None:
        now = time.time()
        with self._lock:
            data = self._load()
            entries = self._recent(data, key, now)
            entries.append(now)
            data[self._storage_key(key)] = list(entries)
            self._save(data)

    def clear(self, key: str) -> None:
        with self._lock:
            data = self._load()
            data.pop(self._storage_key(key), None)
            self._save(data)

    def reset(self) -> None:
        with self._lock:
            data = self._load()
            prefix = f"{self.namespace}:"
            data = {key: value for key, value in data.items() if not key.startswith(prefix)}
            self._save(data)

    def _storage_key(self, key: str) -> str:
        return f"{self.namespace}:{key}"

    def _recent(self, data: dict[str, list[float]], key: str, now: float) -> deque[float]:
        storage_key = self._storage_key(key)
        entries = deque(float(item) for item in data.get(storage_key, []))
        while entries and now - entries[0] > self.window_seconds:
            entries.popleft()
        data[storage_key] = list(entries)
        return entries

    def _load(self) -> dict[str, list[float]]:
        try:
            with self.store_path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
        if not isinstance(raw, dict):
            return {}
        return defaultdict(list, {str(key): value for key, value in raw.items() if isinstance(value, list)})

    def _save(self, data: dict[str, list[float]]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.store_path.with_suffix(f"{self.store_path.suffix}.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, separators=(",", ":"))
        temp_path.replace(self.store_path)


def client_ip(request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"
