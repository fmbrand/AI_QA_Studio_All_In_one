"""A small in-process sliding-window rate limiter.

Good enough for a single API process. A multi-instance deployment needs a shared store
(Redis or PostgreSQL); the interface stays the same.
"""

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: float = 60.0) -> tuple[bool, int]:
        """Record a hit. Return (allowed, retry_after_seconds)."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return False, max(1, int(hits[0] + window_seconds - now) + 1)
            hits.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


login_limiter = RateLimiter()
