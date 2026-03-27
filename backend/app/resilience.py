# backend/app/resilience.py
import asyncio
import random
import time
import functools
import logging

logger = logging.getLogger(__name__)


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 300):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._is_open = False

    @property
    def is_open(self) -> bool:
        if self._is_open and (time.time() - self._last_failure_time > self._recovery_timeout):
            self._is_open = False
            self._failure_count = 0
        return self._is_open

    def check(self):
        if self.is_open:
            raise CircuitOpenError(
                f"Circuit open — {self._recovery_timeout}s recovery, "
                f"last failure {time.time() - self._last_failure_time:.0f}s ago"
            )

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self._failure_threshold:
            self._is_open = True
            logger.warning(f"Circuit breaker OPEN after {self._failure_count} failures")

    def record_success(self):
        self._failure_count = 0
        self._is_open = False


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = base_delay * (4 ** attempt) + random.uniform(0, base_delay)
                        logger.warning(
                            f"{func.__name__} attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {delay:.1f}s"
                        )
                        await asyncio.sleep(delay)
            raise last_exception
        return wrapper
    return decorator
