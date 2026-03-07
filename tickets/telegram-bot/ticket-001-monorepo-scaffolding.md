**title**: Monorepo scaffolding with backend project structure for Telegram bot architecture
**status**: DONE
**agent**: backend-developer
**depends-on**: None
**blocks**: ticket-002, ticket-003, ticket-006, ticket-010, ticket-011

## Problem
The project is a flat CLI script (`kindle_send.py`). We need a proper backend project structure for the Telegram Bot + Mini App architecture. No separate frontend framework needed for the Mini App (it will be lightweight HTML/JS served by FastAPI).

## Requirements
- [x] Create `backend/` directory with FastAPI project structure using `uv init`
- [x] Create `backend/app/` with subdirectories: `api/`, `services/`, `models/`, `schemas/`, `core/`, `i18n/`
- [x] Create `backend/app/core/config.py` with pydantic-settings `Settings` class:
  - `DATABASE_URL` (PostgreSQL async URL)
  - `REDIS_URL` (for ARQ task queue)
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_WEBHOOK_URL` (public URL for webhook)
  - `TELEGRAM_WEBHOOK_SECRET` (for verifying webhook requests)
  - `TELEGRAM_PAYMENT_PROVIDER_TOKEN` (Stripe via Telegram)
  - `SUBSCRIPTION_PRICE_CENTS` (499 = $4.99)
  - `FREE_TIER_LIMIT` (5)
  - `APP_PORT` (8100)
  - `BASE_URL` (public base URL for Mini App and webhook)
  - `TEMP_DIR` (for temporary EPUB files)
  - `LOG_LEVEL`
- [x] Create `backend/app/main.py` with FastAPI app, CORS middleware (for Mini App), health endpoint `/health`
- [x] Create `backend/pyproject.toml` with Python 3.12+ and dependencies:
  - fastapi, uvicorn[standard], sqlalchemy[asyncio], alembic, asyncpg, pydantic, pydantic-settings
  - python-telegram-bot[webhooks], httpx, arq
  - readability-lxml, beautifulsoup4, lxml, ebooklib, Pillow
  - prometheus-client
  - `pip install git+https://github.com/v-v-l/logs-flow.git#subdirectory=packages/python` (logs-flow)
- [x] Create `landing/` directory for static landing page (plain HTML/CSS/JS, served separately or by nginx)
- [x] Create `miniapp/` directory for Telegram Mini App (plain HTML/CSS/JS, served by FastAPI static files)
- [x] Create `docker-compose.yml` at project root with PostgreSQL 18 (port 5432), Redis (port 6379)
- [x] Create `.env.example` with all expected environment variables
- [x] Move `kindle_send.py` and `requirements.txt` to `legacy/` directory for reference
- [x] Add `.gitignore` for Python monorepo (no Node.js needed)

## Scope
- `backend/` -- full directory tree creation
- `landing/` -- static landing page directory (empty placeholder `index.html`)
- `miniapp/` -- Mini App directory (empty placeholder `index.html`)
- `docker-compose.yml` -- PostgreSQL + Redis
- `.env.example` -- environment variable template
- `.gitignore` -- Python-focused ignore rules
- `legacy/` -- archive original CLI script

## Notes
- Backend port must be 8100 per CLAUDE.md
- Use `uv` as Python package manager
- No Next.js frontend -- the Mini App is lightweight HTML/CSS/JS served as static files by FastAPI
- The landing page is also static HTML -- no framework needed
- python-telegram-bot requires `[webhooks]` extra for webhook support (includes `tornado` or use with FastAPI)
- We use FastAPI to serve both the API and the Mini App static files
