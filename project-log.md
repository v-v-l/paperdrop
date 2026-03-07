# Project Log


## [ticket-002] Database schema and migrations for Telegram bot users, conversions, and subscriptions
- **Agent:** backend-developer
- **Status:** DONE
- **Dependencies:** None
- **Blocks:** None
- **Files:** No git changes detected
- **Timestamp:** 2026-03-07-09-37

### Notes
Created 3 SQLAlchemy async models (User, Conversion, Subscription) with proper constraints. User.id is BigInteger PK (Telegram ID, no autoincrement). Status fields use Python str enums mapped to String columns. All timestamps use timezone with server_default=func.now(). Indexes: ix_conversions_user_id, ix_conversions_user_id_created_at, ix_subscriptions_user_id_status. Subscription.user_id has UNIQUE constraint. Created async database.py with engine + session factory. Initialized Alembic with async template. Migration verification: UP passed, DOWN passed, UP again passed. Fixed docker-compose.yml postgres volume mount for PostgreSQL 18 compatibility.

---

## [ticket-004] Playwright browser fallback for JavaScript-heavy pages
- **Agent:** backend-developer
- **Status:** DONE
- **Dependencies:** None
- **Blocks:** None
- **Files:** No git changes detected
- **Timestamp:** 2026-03-07-09-48

### Notes
Added Playwright browser fallback for JS-heavy pages. Created browser_fetcher.py with fetch_with_browser(). Integrated into pipeline.py: validator runs after HTTP fetch, if it fails and PLAYWRIGHT_ENABLED=True, retries with headless Chromium. Added PLAYWRIGHT_ENABLED config flag to settings. Installed playwright and chromium browser.

---

## [ticket-005] ARQ background task queue for conversion jobs
- **Agent:** backend-developer
- **Status:** done
- **Dependencies:** None
- **Blocks:** None
- **Files:** No git changes detected
- **Timestamp:** 2026-03-07-09-51

### Notes
Implemented ARQ background task queue: worker.py with WorkerSettings (120s timeout, 5 max jobs, startup/shutdown hooks for DB engine + Telegram bot), conversion_task.py with process_conversion that creates DB record, runs pipeline, updates status, sends EPUB via bot.send_document, deletes temp files, handles errors with user notification. tasks/__init__.py exports enqueue_conversion helper.

---

## [ticket-011] Static landing page with value proposition and bot link
- **Agent:** backend-developer
- **Status:** DONE
- **Dependencies:** None
- **Blocks:** None
- **Files:** No git changes detected
- **Timestamp:** 2026-03-07-11-06

### Notes
Created all 4 landing page files: index.html (hero, how-it-works, comparison table, pricing cards, privacy highlights, CTA, footer), privacy.html (11-section privacy policy with GDPR rights), terms.html (12-section ToS with personal-use disclaimer, content ownership, termination clause), style.css (vanilla CSS with light/dark mode via prefers-color-scheme, mobile-responsive grid layouts, sticky nav, pricing cards with featured badge). All pages include SEO meta tags and Open Graph tags. BOT_USERNAME placeholder used throughout.

---
