import math
import time
from collections import defaultdict, deque
from threading import Lock


class InMemoryRateLimiter:
    def __init__(self, limit: int, window_seconds: int = 60):
        if limit < 1:
            raise ValueError("Rate limit must be at least 1.")
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, now: float | None = None):
        current_time = time.monotonic() if now is None else now
        cutoff = current_time - self.window_seconds

        with self._lock:
            requests = self._requests[key]
            while requests and requests[0] <= cutoff:
                requests.popleft()

            if len(requests) >= self.limit:
                retry_after = max(
                    1, math.ceil(self.window_seconds - (current_time - requests[0]))
                )
                return False, 0, retry_after

            requests.append(current_time)
            remaining = self.limit - len(requests)
            return True, remaining, 0
