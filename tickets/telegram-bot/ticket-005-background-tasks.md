**title**: ARQ background task queue for conversion jobs
**agent**: backend-developer
**depends-on**: ticket-002, ticket-003, ticket-004
**blocks**: ticket-006

## Problem
URL-to-EPUB conversion is slow (5-30 seconds depending on images and Playwright). It must run in a background worker, not in the request/bot handler. ARQ (async Redis queue) handles job dispatch and execution.

## Requirements
- [ ] Create `backend/app/worker.py` -- ARQ worker entry point with `WorkerSettings` class:
  - Redis connection from settings
  - Job timeout: 120 seconds
  - Max concurrent jobs: 5
  - Health check key in Redis
- [ ] Create `backend/app/services/tasks/conversion_task.py`:
  - `async def process_conversion(ctx, user_id: int, url: str, chat_id: int, message_id: int, grayscale: bool = True)`:
    1. Create `Conversion` record in DB with status `processing`
    2. Call `convert_url()` pipeline
    3. On success: update conversion record (title, author, file_size, image_count, used_playwright, status=completed), increment `User.total_conversions`
    4. Send EPUB file back to user via Telegram Bot API (using `bot.send_document()`)
    5. Delete temporary EPUB file
    6. On failure: update conversion status to `failed`, set error_message, notify user via Telegram message
  - The task needs access to: DB session, Telegram bot instance, conversion pipeline
- [ ] Create `backend/app/services/tasks/__init__.py` exporting task functions
- [ ] Add job dispatch helper: `async def enqueue_conversion(redis, user_id, url, chat_id, message_id, grayscale)` that enqueues the ARQ job
- [ ] ARQ worker must initialize on startup: DB engine, Telegram bot instance, httpx client
- [ ] ARQ worker must cleanup on shutdown: close DB engine, close bot, close httpx client

## Scope
- `backend/app/worker.py` -- ARQ worker settings and startup/shutdown hooks
- `backend/app/services/tasks/__init__.py`
- `backend/app/services/tasks/conversion_task.py`

## Notes
- ARQ uses Redis as broker -- reuse the Redis from docker-compose
- The worker runs as a separate process: `arq backend.app.worker.WorkerSettings`
- The task sends the EPUB file via Telegram Bot API -- it needs the bot token to create a Bot instance
- `chat_id` and `message_id` are needed to reply to the user's original message
- File sending: use `bot.send_document(chat_id=chat_id, document=open(epub_path, 'rb'), filename=f"{title}.epub", reply_to_message_id=message_id)`
- After sending, immediately delete the temp EPUB file (privacy-first)
- If sending fails (file too large for Telegram's 50MB limit), notify user with error message
- Worker should log each job start/complete/fail with timing using logs-flow
