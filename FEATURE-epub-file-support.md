# Feature: Accept EPUB and PDF File Attachments

**Type:** Feature request
**Priority:** High
**Product:** PaperDrop (@PaperDrop_bot)
**Date:** 2026-03-07

## Summary

PaperDrop currently only accepts URLs. Add support for **EPUB** and **PDF** file attachments. User sends or forwards a file to the bot, the bot validates it, processes it through the appropriate backend service, sends the resulting EPUB back in chat, and delivers to Kindle if configured.

This turns PaperDrop into a universal **"send anything to Kindle"** tool:
- **URL** → existing pipeline (fetch → extract → EPUB)
- **EPUB** → validate → fix via EPUB Fixer API → deliver
- **PDF** → convert via PDF-to-EPUB API (reflow mode) → deliver

## User Flows

### EPUB Flow
```
User sends/forwards .epub file to @PaperDrop_bot
  → Bot downloads the file from Telegram
  → Validation:
      1. Is it a valid ZIP? (reject if not)
      2. Does it contain META-INF/encryption.xml with DRM? (reject with explanation)
      3. Is it under size limit? (reject if too large)
  → Send file to EPUB Fixer API: POST http://<epub-fixer>/convert (multipart/form-data)
  → Get fixed EPUB back
  → Send fixed EPUB as document in Telegram chat (reply to original message)
  → If user has kindle_email configured: send to Kindle via existing kindle_sender
  → Log as conversion (counts toward free tier / rate limits)
```

### PDF Flow
```
User sends/forwards .pdf file to @PaperDrop_bot
  → Bot downloads the file from Telegram
  → Validation:
      1. File starts with %PDF magic bytes? (reject if not)
      2. Is it under size limit? (reject if too large)
  → Send file to PDF-to-EPUB API: POST http://<pdf-to-epub>/api/convert (multipart/form-data)
      mode=reflow, author=Unknown (no vision mode, no AI costs)
  → Get EPUB back
  → Send EPUB as document in Telegram chat (reply to original message)
  → If user has kindle_email configured: send to Kindle via existing kindle_sender
  → Log as conversion (counts toward free tier / rate limits)
```

## Implementation Details

### 1. New handler: `document_handler` in `handlers.py`

A single handler that routes based on file type.

```python
# In bot.py, register alongside url_message_handler:
from telegram.ext import filters

epub_filter = filters.Document.MimeType("application/epub+zip") | filters.Document.FileExtension("epub")
pdf_filter = filters.Document.MimeType("application/pdf") | filters.Document.FileExtension("pdf")

app.add_handler(MessageHandler(epub_filter | pdf_filter, document_handler))
```

The handler should:
- Download the file via `await update.message.document.get_file()` then `await file.download_as_bytearray()`
- Detect file type from extension or mime_type
- Run type-specific validation (see below)
- Enqueue the appropriate ARQ job

### 2. Validation

#### EPUB validation (in handler, before enqueuing)

**Check 1: Valid ZIP with mimetype file**
```python
import zipfile, io

if not zipfile.is_zipfile(io.BytesIO(file_bytes)):
    # Reply with "epub_invalid_format" i18n string
    return

with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as zf:
    names = zf.namelist()
    has_mimetype = "mimetype" in names or any(
        n.endswith("/mimetype") and n.count("/") == 1 for n in names
    )
    if not has_mimetype:
        # Reply with "epub_no_mimetype" i18n string
        return
```

**Check 2: DRM detection**
```python
    has_drm = False
    if "META-INF/encryption.xml" in names:
        encryption_xml = zf.read("META-INF/encryption.xml").decode("utf-8", errors="ignore")
        if "EncryptedData" in encryption_xml:
            has_drm = True

    if has_drm:
        # Reply with "epub_drm_protected" i18n string
        return
```

#### PDF validation (in handler, before enqueuing)

**Check 1: PDF magic bytes**
```python
if not file_bytes[:5] == b"%PDF-":
    # Reply with "pdf_invalid_format" i18n string
    return
```

That's it for PDFs. The PDF-to-EPUB service handles everything else (corrupt pages, empty text, etc.) and returns meaningful errors.

**Check 2: File size** — Telegram caps file downloads at 20MB for bots (50MB with local Bot API server). Both backend services enforce 50MB limits.

### 3. New ARQ task: `process_file` in `tasks/`

Create `tasks/file_task.py` alongside existing `conversion_task.py`.

One task handles both file types to avoid duplication — the only difference is which API to call.

```python
async def process_file(
    ctx: dict,
    user_id: int,
    chat_id: int,
    message_id: int,
    file_bytes: bytes,
    filename: str,
    file_type: str,  # "epub" or "pdf"
) -> None:
```

Steps:
1. Create a Conversion record (use filename as `title`, set `url` to `file://{filename}`)
2. Call the appropriate API:
   ```python
   async with httpx.AsyncClient(timeout=120.0) as client:
       if file_type == "epub":
           response = await client.post(
               settings.EPUB_FIXER_URL,
               files={"file": (filename, file_bytes, "application/epub+zip")},
           )
       elif file_type == "pdf":
           response = await client.post(
               settings.PDF_TO_EPUB_URL,
               files={"file": (filename, file_bytes, "application/pdf")},
               data={"mode": "reflow", "author": "Unknown"},
           )
       response.raise_for_status()
       epub_bytes = response.content
   ```
3. Save EPUB to temp file
4. Send as document via Telegram bot (reply to original message)
5. Send to Kindle if `user.kindle_email` is configured (reuse existing `send_to_kindle()`)
6. Update Conversion record, increment `user.total_conversions`
7. Clean up temp file

**Important:** Use `timeout=120.0` for the HTTP client. PDF conversion (reflow mode) can take 10-30 seconds for large documents. EPUB fixing is near-instant.

### 4. New config variables

Add to `config.py`:
```python
# File processing APIs (internal network)
EPUB_FIXER_URL: str = "http://localhost:8010/convert"
PDF_TO_EPUB_URL: str = "http://localhost:8100/api/convert"
```

In production, these should point to the services on the internal network.

### 5. Rate limiter bypass for backend services

**EPUB Fixer** has a rate limiter (1 req/60s per IP). Since PaperDrop calls server-to-server, all requests share one IP.

**Solution:** Set `RATE_LIMIT_REQUESTS=100` and `RATE_LIMIT_WINDOW=60` on the EPUB Fixer service via env vars. PaperDrop already has its own per-user rate limiting (3 req/hr free, 20 req/hr paid), so abuse is already prevented.

**PDF-to-EPUB** has no rate limiter — no changes needed there.

### 6. Conversion model consideration

The `Conversion` model has a required `url` field (`nullable=False`). For file uploads:
- Store `file://{filename}` as the URL — no migration needed
- The `title` field gets the filename (without extension)

### 7. Enqueue helper

Add `enqueue_file` to `tasks/__init__.py`:
```python
async def enqueue_file(
    redis: ArqRedis,
    user_id: int,
    chat_id: int,
    message_id: int,
    file_bytes: bytes,
    filename: str,
    file_type: str,  # "epub" or "pdf"
) -> None:
    await redis.enqueue_job(
        "process_file",
        user_id=user_id,
        chat_id=chat_id,
        message_id=message_id,
        file_bytes=file_bytes,
        filename=filename,
        file_type=file_type,
    )
```

Register `process_file` in `worker.py`'s `WorkerSettings.functions`.

### 8. i18n strings

Add to `i18n/locales/en/bot.json`:
```json
{
  "file_processing_epub": "Got your EPUB! Checking and preparing for Kindle...",
  "file_processing_pdf": "Got your PDF! Converting to EPUB for Kindle... This may take a moment.",
  "epub_invalid_format": "This doesn't look like a valid EPUB file.",
  "epub_no_mimetype": "This file doesn't appear to be a valid EPUB (missing mimetype).",
  "epub_drm_protected": "This EPUB is DRM-protected. Only DRM-free EPUBs can be sent to Kindle.",
  "pdf_invalid_format": "This doesn't look like a valid PDF file.",
  "file_fix_failed": "Failed to process this file. It might be corrupted or in an unsupported format.",
  "file_delivered": "Your file is ready! See the EPUB above.",
  "file_kindle_sent": "Delivered to your Kindle ({kindle_email})",
  "file_kindle_failed": "Couldn't deliver to Kindle ({kindle_email}). You can forward the EPUB above manually."
}
```

### 9. Update /help and /start messages

Update the `welcome` and `help` i18n strings to mention file support:

```
Send me:
- A link to any article
- An EPUB file (I'll fix it and deliver to your Kindle)
- A PDF file (I'll convert it to EPUB for your Kindle)
```

## What NOT to change

- URL conversion flow — untouched, works as before
- Subscription/payment logic — file uploads count as conversions (same limits apply)
- Rate limiting — existing per-user rate limits apply equally to file uploads
- Kindle sender — reuse as-is, it already accepts an epub_path and title

## Testing

New tests to add:
- `test_document_handler_valid_epub` — happy path, EPUB processed and returned
- `test_document_handler_valid_pdf` — happy path, PDF converted and returned
- `test_document_handler_invalid_zip` — not a ZIP file, gets rejection
- `test_document_handler_drm_protected` — encryption.xml with EncryptedData, gets rejection
- `test_document_handler_no_mimetype` — ZIP without mimetype file, gets rejection
- `test_document_handler_invalid_pdf` — not a PDF, gets rejection
- `test_process_file_epub_task` — ARQ task with mocked EPUB Fixer API
- `test_process_file_pdf_task` — ARQ task with mocked PDF-to-EPUB API
- `test_process_file_kindle_delivery` — end-to-end with Kindle sending
- `test_process_file_api_timeout` — backend service timeout handled gracefully
- `test_file_counts_toward_free_tier` — conversion increments total_conversions

## Verification

After implementation:
1. Send a valid EPUB → should receive fixed EPUB back + Kindle delivery
2. Send a PDF → should receive converted EPUB back + Kindle delivery
3. Forward a message with EPUB/PDF attachment from another chat → same result
4. Send a DRM-protected EPUB → should get rejection message
5. Send a random file renamed to .epub → should get "not valid EPUB" message
6. Send a random file renamed to .pdf → should get "not valid PDF" message
7. Check that file uploads count toward free tier limit
8. Send a large PDF (50+ pages) → should complete within timeout, not hang
9. Verify /help text mentions file support
