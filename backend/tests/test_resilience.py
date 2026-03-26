# backend/tests/test_resilience.py
import pytest
from app.resilience import retry_with_backoff, CircuitBreaker, CircuitOpenError

@pytest.mark.asyncio
async def test_retry_succeeds_on_first_try():
    call_count = 0
    @retry_with_backoff(max_retries=3, base_delay=0.01)
    async def always_works():
        nonlocal call_count
        call_count += 1
        return "ok"
    result = await always_works()
    assert result == "ok"
    assert call_count == 1

@pytest.mark.asyncio
async def test_retry_succeeds_after_failures():
    call_count = 0
    @retry_with_backoff(max_retries=3, base_delay=0.01)
    async def fails_twice():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("fail")
        return "ok"
    result = await fails_twice()
    assert result == "ok"
    assert call_count == 3

@pytest.mark.asyncio
async def test_retry_exhausted():
    @retry_with_backoff(max_retries=2, base_delay=0.01)
    async def always_fails():
        raise ConnectionError("fail")
    with pytest.raises(ConnectionError):
        await always_fails()

def test_circuit_breaker_opens_after_failures():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
    for _ in range(3):
        cb.record_failure()
    assert cb.is_open is True

def test_circuit_breaker_allows_when_closed():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
    cb.record_failure()
    assert cb.is_open is False

def test_circuit_breaker_resets_on_success():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    assert cb.is_open is False
    assert cb._failure_count == 0

def test_circuit_open_error():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=300)
    cb.record_failure()
    with pytest.raises(CircuitOpenError):
        cb.check()
