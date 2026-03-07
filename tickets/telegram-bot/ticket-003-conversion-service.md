**title**: Refactor CLI conversion logic into modular async service
**agent**: backend-developer
**depends-on**: ticket-001
**blocks**: ticket-004, ticket-005

## Problem
The existing `kindle_send.py` has the core conversion pipeline (URL fetch, readability extraction, image processing, EPUB building). This needs to be refactored into a clean async service module that can be called from the ARQ background worker.

## Requirements
- [x] Create `backend/app/services/conversion/` package with clear separation:
  - `fetcher.py` -- async HTTP fetch with browser UA (ported from `fetch_page()`)
  - `extractor.py` -- readability extraction + metadata (ported from `extract_article()`, `clean_title()`)
  - `image_processor.py` -- image download, resize, compress (ported from `resolve_url()`, `download_and_optimize_image()`, `process_images()`)
  - `epub_builder.py` -- EPUB assembly (ported from `build_epub()`, `slugify()`)
  - `validator.py` -- content validation (checks extraction quality, triggers fallback decision)
  - `pipeline.py` -- orchestrates the full pipeline: fetch -> extract -> validate -> images -> EPUB
- [x] Port all functions from `legacy/kindle_send.py` to respective modules:
  - Replace `print()` with logs-flow logger
  - Make functions async where doing I/O (use `httpx` instead of `requests`)
  - Return structured results instead of printing
  - Accept configuration via function parameters, not global constants
- [x] `pipeline.py` exposes async function:
  ```python
  async def convert_url(url: str, output_dir: str, grayscale: bool = True) -> ConversionResult
  ```
  where `ConversionResult` is a dataclass with: `epub_path`, `title`, `author`, `image_count`, `file_size_bytes`, `used_playwright`
- [x] `validator.py` checks:
  - Content is not empty
  - Extracted text length > 200 characters
  - Title was extracted (not just the domain name)
  - Returns `ValidationResult` with `passed: bool`, `reason: str`
- [x] Temporary EPUB files go to configurable temp directory, caller responsible for cleanup
- [x] Image processing (PIL operations) runs in executor via `asyncio.to_thread()`

## Scope
- `backend/app/services/conversion/__init__.py`
- `backend/app/services/conversion/fetcher.py`
- `backend/app/services/conversion/extractor.py`
- `backend/app/services/conversion/image_processor.py`
- `backend/app/services/conversion/epub_builder.py`
- `backend/app/services/conversion/validator.py`
- `backend/app/services/conversion/pipeline.py`

## Notes
- Reference implementation: `legacy/kindle_send.py` (original CLI script)
- Key constants to make configurable: `MAX_IMAGE_WIDTH=1200`, `IMAGE_QUALITY=80`, `REQUEST_TIMEOUT=20`, `MAX_EPUB_SIZE_MB=48`
- The `grayscale` parameter default is True (most users want Kindle-optimized grayscale)
- Image processing is CPU-bound -- run PIL operations in thread executor
- `fetcher.py` should return raw HTML + response metadata (status code, content type, final URL after redirects)
- Do NOT include email/SMTP sending -- the bot sends files directly in Telegram chat
- The pipeline should NOT catch exceptions -- let the caller (ARQ worker) handle errors and update conversion status
