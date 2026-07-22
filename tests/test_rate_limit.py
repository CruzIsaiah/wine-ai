import pytest

from rate_limit import InMemoryRateLimiter


def test_rate_limiter_blocks_requests_over_limit():
    limiter = InMemoryRateLimiter(limit=2, window_seconds=60)

    assert limiter.allow("client", now=0) == (True, 1, 0)
    assert limiter.allow("client", now=1) == (True, 0, 0)
    allowed, remaining, retry_after = limiter.allow("client", now=2)

    assert allowed is False
    assert remaining == 0
    assert retry_after == 58


def test_rate_limiter_resets_after_window():
    limiter = InMemoryRateLimiter(limit=1, window_seconds=60)
    limiter.allow("client", now=0)

    assert limiter.allow("client", now=60) == (True, 0, 0)


def test_rate_limiter_rejects_invalid_limit():
    with pytest.raises(ValueError, match="at least 1"):
        InMemoryRateLimiter(limit=0)
