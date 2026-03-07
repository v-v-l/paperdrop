# PaperDrop

Telegram bot that converts web articles, EPUBs, and PDFs to Kindle-ready EPUB files with automatic Kindle delivery. Deployed at `paperdrop.bp-flow.com`, bot is `@PaperDrop_bot`.

## Quick Reference

```bash
# Run tests (86 tests, ~0.7s)
cd backend && uv run pytest tests/ -x -q

# Run locally (Docker)
docker compose up -d --build

# Run locally (dev, no Docker)
cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8040 --reload

# Run worker separately
cd backend && uv run arq app.worker.WorkerSettings

# Run migrations
cd backend && uv run alembic upgrade head

# Create migration
cd backend && uv run alembic revision --autogenerate -m "description"

# Rebuild & deploy (production)
docker compose up -d --force-recreate --build
```

## Architecture

```
User sends URL / EPUB / PDF to @PaperDrop_bot
  -> Telegram webhook -> FastAPI (/api/telegram/webhook)
    -> handler validates input, checks rate limit + free tier, enqueues ARQ job via Redis

URL path:
  -> worker: fetch HTML -> extract article -> validate -> Playwright fallback
     -> process images -> build EPUB -> send in chat -> Kindle delivery

EPUB path:
  -> worker: call EPUB Fixer API (http://host:8010/convert) -> send fixed EPUB -> Kindle

PDF path:
  -> worker: call PDF-to-EPUB API (http://host:PORT/api/convert, reflow mode) -> send EPUB -> Kindle
```

**Services** (docker-compose):
- `backend` — FastAPI app (port 8040), serves webhook + Mini App API + static miniapp files
- `worker` — ARQ worker, same Docker image, different entrypoint (`arq app.worker.WorkerSettings`)
- `redis` — Redis 7, used for ARQ task queue + rate limiting
- `landing` — nginx serving static landing page (port 8080)
- `migrate` — one-shot container running Alembic migrations

**External services:**
- PostgreSQL 18 — prod DB at `192.168.100.75:5437/paperdrop_prod`
- EPUB Fixer — `192.168.100.70:8010` (same machine), `POST /convert`
- PDF-to-EPUB — not deployed yet, `POST /api/convert` with `mode=reflow`
- Caddy reverse proxy — separate machine, auto-HTTPS for `paperdrop.bp-flow.com`

## Project Structure

```
backend/
  app/
    main.py                          # FastAPI app + lifespan (bot init/shutdown)
    worker.py                        # ARQ worker settings + startup/shutdown
    core/
      config.py                      # Pydantic Settings (.env from project root)
      database.py                    # SQLAlchemy async engine + session factory
      metrics.py                     # Prometheus counters/histograms
    models/                          # SQLAlchemy models
      user.py                        # User (PK = Telegram user ID)
      conversion.py                  # Conversion (tracks each URL conversion)
      subscription.py                # Subscription (1:1 with User, 30-day periods)
    api/
      webhook.py                     # POST /api/telegram/webhook
      miniapp.py                     # Mini App REST API (auth, settings, history, subscription)
      metrics.py                     # GET /metrics (Prometheus)
    services/
      telegram/
        bot.py                       # Bot application factory, webhook setup/teardown, handler registration
        handlers.py                  # Command, URL, document, and payment handlers
        auth.py                      # Telegram initData HMAC-SHA256 validation
        url_utils.py                 # URL extraction and validation
        strings.py                   # Legacy string constants (pre-i18n)
      conversion/
        pipeline.py                  # Orchestrator: fetch -> extract -> validate -> images -> EPUB
        fetcher.py                   # HTTP fetch with httpx
        browser_fetcher.py           # Playwright fallback for JS-heavy pages
        extractor.py                 # readability-lxml article extraction
        image_processor.py           # Image download, resize, grayscale (Pillow)
        epub_builder.py              # EPUB assembly (ebooklib)
        validator.py                 # Content quality validation
      tasks/
        __init__.py                  # enqueue_conversion() + enqueue_file() helpers
        conversion_task.py           # ARQ task: URL -> EPUB pipeline + delivery
        file_task.py                 # ARQ task: EPUB/PDF -> external API -> delivery
      payments/
        subscription_service.py      # create/check/can_convert subscription logic
      email/
        kindle_sender.py             # Send EPUB to Kindle via Resend API
      rate_limiter.py                # Redis sliding-window rate limiter
    schemas/miniapp.py               # Pydantic request/response models
    i18n/
      __init__.py                    # get_text() helper with {var} interpolation
      locales/en/bot.json            # Bot message translations
  miniapp/                           # Static Mini App (HTML/CSS/JS)
    index.html, style.css, app.js, i18n.js
    locales/en.json                  # Mini App UI translations
  migrations/                        # Alembic migrations
  tests/                             # pytest, mirrors app/ structure
landing/                             # Static landing page (nginx)
  index.html, privacy.html, terms.html
caddy/Caddyfile                      # Reverse proxy config (on gateway machine)
```

## Key Patterns

- **Config**: `app.core.config.settings` — Pydantic Settings loading `.env` from project root (3 parents above `config.py`)
- **DB sessions**: use `async with async_session_factory() as session:` in handlers, or `session_factory` from `ctx` in worker tasks
- **Logging**: always use `logs_flow` — `create_logger(service="name")`, `format_error(exc)`, `ErrorCodes.XXX`
- **i18n**: `get_text(locale, module, key, **kwargs)` — translations in `i18n/locales/{lang}/{module}.json`. Miniapp has its own `locales/en.json`
- **Bot handlers**: registered in `bot.py:create_bot_application()`, implemented in `handlers.py`. Use `_t(update, key)` for i18n
- **Three input types**: URLs (conversion pipeline), EPUBs (EPUB Fixer API), PDFs (PDF-to-EPUB API). All share rate limiting, free tier checks, Kindle delivery, and conversion tracking
- **File validation**: EPUB — valid ZIP + has `mimetype` + no DRM. PDF — `%PDF-` magic bytes. Done in handler before enqueuing
- **Payments**: Telegram Stars (currency `XTR`, empty `provider_token`), 250 Stars = Pro for 30 days
- **User model**: PK is Telegram user ID (BigInteger), has `kindle_email`, `grayscale_images`, `total_conversions`
- **Subscription**: 1:1 with User (unique constraint on `user_id`), auto-expires on check via `check_subscription()`
- **Kindle delivery**: after EPUB sent in chat, emails to `user.kindle_email` via Resend if configured. Always shows transparent status message (success or failure)
- **Branding**: product is called "PaperDrop" everywhere user-facing. Internal identifiers use `links_to_epub`

## Environment Variables

Required in `.env` (project root):
- `TELEGRAM_BOT_TOKEN` — from @BotFather
- `TELEGRAM_WEBHOOK_URL` — public HTTPS URL (e.g., `https://paperdrop.bp-flow.com`)
- `TELEGRAM_WEBHOOK_SECRET` — arbitrary secret for webhook verification
- `DATABASE_URL` — PostgreSQL async connection string (prod: `192.168.100.75:5437/paperdrop_prod`)
- `REDIS_URL` — Redis connection string

Optional:
- `RESEND_API_KEY` — enables Send-to-Kindle via email (domain must be verified in Resend dashboard)
- `SENDER_EMAIL` — from address for Kindle emails (default: `send@paperdrop.bp-flow.com`)
- `EPUB_FIXER_URL` — EPUB Fixer API endpoint (default: `http://192.168.100.70:8010/convert`)
- `PDF_TO_EPUB_URL` — PDF-to-EPUB API endpoint (default: `http://192.168.100.70:8040/api/convert`)
- `PLAYWRIGHT_ENABLED` — `true` enables Playwright fallback for JS-heavy pages
- `MINI_APP_URL` — URL to Mini App (must end with `/`)
- `SUBSCRIPTION_PRICE_STARS` — Telegram Stars price for Pro (default: 250)
- `FREE_TIER_LIMIT` — free conversions before paywall (default: 5)
- `APP_PORT` — backend port (default: 8040)

## Testing

```bash
cd backend && uv run pytest tests/ -x -q
```

- 86 tests, runs in ~0.7s
- Uses SQLite in-memory for DB tests, fakeredis for Redis tests
- No external services needed to run tests

## Gotchas

- `.env` path is resolved as `Path(__file__).resolve().parents[3] / ".env"` from `config.py` — sensitive to file moves
- Docker containers need explicit DNS (`8.8.8.8`) to reach `api.telegram.org`
- `docker compose restart` does NOT reload `.env` — use `docker compose up -d --force-recreate`
- Mini App URL must have trailing slash or Telegram's WebApp won't follow FastAPI's redirect
- Bot commands must be registered via `set_my_commands()` in `setup_webhook()` to show in Telegram's menu
- `strings.py` is legacy (pre-i18n) — bot handlers use `_t()` with JSON locale files, but strings.py still exists
- Resend requires domain verification (DNS records: MX, SPF, DKIM) before emails deliver
- Users must add `SENDER_EMAIL` to their Amazon Approved Personal Document E-mail List for Kindle delivery
- Worker uses `host.docker.internal` to reach EPUB Fixer/PDF-to-EPUB on the host — configured via `extra_hosts` in docker-compose
- Port 8040 chosen to avoid conflicts with other services on `192.168.100.70` (8010=epub-fixer, 8100=occupied)
- File uploads stored as `file://{filename}` in the Conversion `url` field — no migration needed
