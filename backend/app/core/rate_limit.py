import time
from collections import deque
from collections.abc import Callable

MAX_TRACKED_KEYS = 10_000


class SlidingWindowRateLimiter:
    """In-process limiter: at most `limit` hits per key within `window_seconds`."""

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str) -> bool:
        """Record an attempt. Returns False when the attempt exceeds the limit."""
        now = self._clock()
        if len(self._hits) > MAX_TRACKED_KEYS:
            self._forget_idle(now)
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window_seconds:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

    def _forget_idle(self, now: float) -> None:
        cutoff = now - self.window_seconds
        for key in [key for key, hits in self._hits.items() if not hits or hits[-1] <= cutoff]:
            del self._hits[key]
