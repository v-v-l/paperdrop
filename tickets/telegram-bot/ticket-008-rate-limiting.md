**title**: Per-user rate limiting to prevent abuse
**agent**: backend-developer
**depends-on**: ticket-006
**blocks**: None

## Problem
We need per-user rate limits to prevent abuse -- both for the free tier and paid users. Without rate limiting, a single user could overwhelm the conversion worker.

## Requirements
- [x] Create `backend/app/services/rate_limiter.py`:
  - Redis-based sliding window rate limiter
  - `async def check_rate_limit(redis, user_id: int, max_requests: int, window_seconds: int) -> tuple[bool, int]`
    - Returns (allowed, seconds_until_reset)
  - Default limits:
    - Free users: 3 conversions per hour
    - Paid users: 20 conversions per hour
  - Use Redis SORTED SET with timestamps for sliding window
- [x] Integrate rate limit check into URL message handler in `handlers.py`:
  - Check rate limit BEFORE checking free tier / subscription
  - If rate limited, send friendly message: "You're converting too fast. Try again in X minutes."
- [ ] Also add rate limit to the webhook endpoint itself (global, not per-user):
  - 100 requests per second globally to prevent DDoS
  - Use FastAPI middleware or dependency
  - SKIPPED: keeping scope minimal per task instructions

## Scope
- `backend/app/services/rate_limiter.py` -- new file
- `backend/app/services/telegram/handlers.py` -- integrate rate limit check
- `backend/app/api/webhook.py` -- optional global rate limit

## Notes
- Redis sliding window is simple and accurate: ZADD with timestamp score, ZREMRANGEBYSCORE to clean old entries, ZCARD to count
- Rate limit keys: `rate_limit:{user_id}` with TTL matching the window
- Return remaining quota in the rate limit response so the bot message can say "X conversions remaining this hour"
- The global webhook rate limit protects against Telegram retry storms, not normal usage
