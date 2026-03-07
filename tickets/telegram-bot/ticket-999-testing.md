**title**: End-to-end testing of the complete Telegram bot feature set
**status**: DONE
**agent**: backend-developer
**depends-on**: ticket-001, ticket-002, ticket-003, ticket-004, ticket-005, ticket-006, ticket-007, ticket-008, ticket-009, ticket-010, ticket-011, ticket-012, ticket-013

## Problem
Validate the complete Telegram bot application works end-to-end: conversion pipeline, bot handlers, payments, Mini App API, rate limiting, and observability.

## Requirements
- [x] **Conversion pipeline tests** (`backend/tests/services/conversion/`):
  - Test `fetcher.py` with a mock HTTP response
  - Test `extractor.py` with sample HTML (verify title, author, content extraction)
  - Test `image_processor.py` with a sample image (verify resize, grayscale, JPEG output)
  - Test `epub_builder.py` end-to-end (verify valid EPUB output)
  - Test `validator.py` with good and bad content (verify pass/fail logic)
  - Test `pipeline.py` full flow with mocked HTTP (URL -> EPUB file on disk)
  - Test Playwright fallback triggers when validator fails
- [x] **Bot handler tests** (`backend/tests/services/telegram/`):
  - Test URL extraction from messages (plain text, forwarded messages, multiple URLs)
  - Test URL validation (reject invalid URLs, accept valid ones)
  - Test initData signature validation (valid and invalid)
- [x] **Payment tests** (`backend/tests/services/payments/`):
  - Test subscription creation and status check
  - Test `can_convert()` logic: free tier, expired sub, active sub
  - Test subscription expiry detection
- [x] **Mini App API tests** (`backend/tests/api/`):
  - Test `/health` endpoint returns 200
  - Test `/metrics` endpoint returns valid Prometheus format
- [x] **Rate limiter tests** (`backend/tests/services/`):
  - Test sliding window rate limit (allow under limit, block over limit)
  - Test rate limit reset after window expires
- [x] **Metrics tests** (`backend/tests/api/`):
  - Test `/metrics` endpoint returns valid Prometheus format
  - Test `/health` endpoint returns 200
- [x] **Integration check**:
  - Verify all models can be created in test DB (run migrations)
  - Verify all FastAPI routes are registered (no import errors)
- [x] Run full test suite: `cd backend && uv run pytest tests/ -v` -- 76 passed
- [x] If any tests fail, create fix tickets with specific file paths and error details -- all tests pass

## Scope
- `backend/tests/` -- all test files mirroring `app/` structure
- `backend/tests/conftest.py` -- shared fixtures (test DB, mock Redis, mock Telegram bot)

## Notes
- Use `pytest-asyncio` for async test functions
- Use `httpx.AsyncClient` with FastAPI's `TestClient` for API endpoint tests
- Mock external services: Telegram Bot API, Redis (use `fakeredis`), HTTP fetches
- For conversion tests, use saved HTML fixtures (small sample articles)
- Do NOT test against real Telegram API or real URLs -- all external calls must be mocked
- The test DB should use SQLite or a test PostgreSQL instance
- Focus on business logic correctness, not Telegram library internals
