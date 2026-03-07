"""Tests for the Redis-based sliding window rate limiter."""

import pytest

from app.services.rate_limiter import check_rate_limit


async def test_allow_under_limit(fake_redis):
    """Requests under the limit are allowed."""
    allowed, reset = await check_rate_limit(fake_redis, user_id=1, max_requests=3, window_seconds=60)
    assert allowed is True
    assert reset == 0


async def test_block_over_limit(fake_redis):
    """After max_requests, the next one is blocked."""
    for _ in range(3):
        allowed, _ = await check_rate_limit(fake_redis, user_id=2, max_requests=3, window_seconds=60)
        assert allowed is True

    allowed, reset = await check_rate_limit(fake_redis, user_id=2, max_requests=3, window_seconds=60)
    assert allowed is False
    assert reset > 0


async def test_different_users_independent(fake_redis):
    """Rate limits are per-user."""
    for _ in range(3):
        await check_rate_limit(fake_redis, user_id=10, max_requests=3, window_seconds=60)

    # User 10 is at limit
    allowed_10, _ = await check_rate_limit(fake_redis, user_id=10, max_requests=3, window_seconds=60)
    assert allowed_10 is False

    # User 20 is fresh
    allowed_20, _ = await check_rate_limit(fake_redis, user_id=20, max_requests=3, window_seconds=60)
    assert allowed_20 is True


async def test_reset_seconds_positive_when_blocked(fake_redis):
    """When blocked, seconds_until_reset should be >= 1."""
    for _ in range(2):
        await check_rate_limit(fake_redis, user_id=3, max_requests=2, window_seconds=120)

    _, reset = await check_rate_limit(fake_redis, user_id=3, max_requests=2, window_seconds=120)
    assert reset >= 1
