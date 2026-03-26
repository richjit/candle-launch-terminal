import time
from app.cache import MemoryCache, RateLimiter


def test_cache_set_and_get():
    cache = MemoryCache()
    cache.set("key1", {"data": 42}, ttl=60)
    assert cache.get("key1") == {"data": 42}


def test_cache_expired():
    cache = MemoryCache()
    cache.set("key1", "value", ttl=0)
    time.sleep(0.01)
    assert cache.get("key1") is None


def test_cache_miss():
    cache = MemoryCache()
    assert cache.get("nonexistent") is None


def test_rate_limiter_allows():
    limiter = RateLimiter(max_calls=5, period=1.0)
    for _ in range(5):
        assert limiter.allow("source_a") is True


def test_rate_limiter_blocks():
    limiter = RateLimiter(max_calls=2, period=1.0)
    assert limiter.allow("source_a") is True
    assert limiter.allow("source_a") is True
    assert limiter.allow("source_a") is False


def test_rate_limiter_independent_sources():
    limiter = RateLimiter(max_calls=1, period=1.0)
    assert limiter.allow("source_a") is True
    assert limiter.allow("source_b") is True
    assert limiter.allow("source_a") is False
