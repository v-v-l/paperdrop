"""Redis-based sliding window rate limiter.

Uses a Redis SORTED SET per user with timestamps as scores.
Old entries are cleaned on each check, giving an accurate sliding window.
"""

import time

from logs_flow import create_logger

logger = create_logger(service="rate-limiter")


async def check_rate_limit(
    redis,
    user_id: int,
    max_requests: int,
    window_seconds: int,
) -> tuple[bool, int]:
    """Check if a user is within their rate limit.

    Uses a Redis sorted set with member=timestamp, score=timestamp.
    On each call: remove expired entries, count remaining, decide.

    Args:
        redis: Redis connection (ArqRedis or redis.asyncio.Redis).
        user_id: Telegram user ID.
        max_requests: Maximum allowed requests in the window.
        window_seconds: Sliding window size in seconds.

    Returns:
        (allowed, seconds_until_reset):
            allowed -- True if the request is within limits.
            seconds_until_reset -- seconds until the oldest entry
                expires (0 if allowed).
    """
    key = f"rate_limit:{user_id}"
    now = time.time()
    window_start = now - window_seconds

    pipe = redis.pipeline()
    # Remove entries outside the window
    pipe.zremrangebyscore(key, "-inf", window_start)
    # Count current entries
    pipe.zcard(key)
    # Get the oldest entry (to compute reset time)
    pipe.zrange(key, 0, 0, withscores=True)
    results = await pipe.execute()

    current_count = results[1]
    oldest_entries = results[2]

    if current_count >= max_requests:
        # Rate limited -- compute seconds until oldest entry expires
        if oldest_entries:
            oldest_score = oldest_entries[0][1]
            seconds_until_reset = int(oldest_score + window_seconds - now) + 1
            seconds_until_reset = max(1, seconds_until_reset)
        else:
            seconds_until_reset = window_seconds
        return False, seconds_until_reset

    # Allowed -- add this request to the set
    member = f"{now}"
    pipe2 = redis.pipeline()
    pipe2.zadd(key, {member: now})
    pipe2.expire(key, window_seconds)
    await pipe2.execute()

    return True, 0
