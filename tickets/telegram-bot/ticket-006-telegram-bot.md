**title**: Telegram bot handlers and webhook integration with FastAPI
**agent**: backend-developer
**depends-on**: ticket-002, ticket-005
**blocks**: ticket-007, ticket-008, ticket-009

## Problem
The core product experience is a Telegram bot. Users send a URL (or forward a message containing a URL), and the bot converts it to EPUB and sends it back. The bot runs in webhook mode integrated with the FastAPI server.

## Requirements
- [ ] Create `backend/app/services/telegram/bot.py`:
  - Initialize `python-telegram-bot` Application with webhook mode
  - Register all command and message handlers
  - Expose setup/shutdown hooks for FastAPI lifespan
- [ ] Create `backend/app/services/telegram/handlers.py` with handlers:
  - `/start` -- welcome message, create User record if not exists (upsert by Telegram user ID), explain usage
  - `/help` -- usage instructions, privacy info, legal disclaimer
  - `/settings` -- reply with inline button that opens Mini App URL
  - `/history` -- show last 10 conversions as inline list (title, date, status)
  - `/subscribe` -- initiate Telegram payment flow (delegate to ticket-007)
  - `/status` -- show current subscription status and remaining free conversions
  - URL message handler -- detect URLs in messages (text or forwarded), validate, check free-tier limit or subscription, enqueue conversion job, send "processing..." acknowledgment
- [ ] Create `backend/app/services/telegram/url_utils.py`:
  - `extract_urls(text: str) -> list[str]` -- regex to find URLs in message text
  - `is_valid_url(url: str) -> bool` -- basic URL validation (http/https, not localhost)
- [ ] Create `backend/app/api/webhook.py`:
  - POST `/api/telegram/webhook` -- receives Telegram updates, passes to bot Application
  - Verify webhook secret header for security
- [ ] Register webhook endpoint in FastAPI app
- [ ] On FastAPI startup: set Telegram webhook URL via Bot API
- [ ] On FastAPI shutdown: clean up bot resources
- [ ] User creation/lookup: on any interaction, ensure User exists in DB (get-or-create pattern)
- [ ] Free tier check: before enqueuing conversion, check `User.total_conversions < FREE_TIER_LIMIT` or active subscription

## Scope
- `backend/app/services/telegram/__init__.py`
- `backend/app/services/telegram/bot.py` -- bot initialization and lifecycle
- `backend/app/services/telegram/handlers.py` -- all command and message handlers
- `backend/app/services/telegram/url_utils.py` -- URL extraction and validation
- `backend/app/api/webhook.py` -- webhook endpoint
- `backend/app/main.py` -- modify to integrate bot lifecycle and webhook route

## Notes
- python-telegram-bot v20+ is async-native and integrates well with FastAPI
- Webhook mode (not polling) -- the bot receives updates via HTTP POST to our endpoint
- The webhook URL must be HTTPS in production. For local dev, use ngrok or similar.
- All user-facing strings must go through i18n (ticket-013), but for now use constants that can be replaced later
- The URL handler should handle both: direct URL messages and forwarded messages containing URLs
- When user hits free tier limit, show a friendly message with /subscribe option
- Rate limiting (ticket-008) will be added on top of the URL handler later
- Message handler priority: commands first, then URL detection in plain messages
- For `/history`, use Telegram's inline keyboard with pagination if >10 items
