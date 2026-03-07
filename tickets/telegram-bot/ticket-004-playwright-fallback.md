**title**: Playwright browser fallback for JavaScript-heavy pages
**agent**: backend-developer
**depends-on**: ticket-003
**blocks**: ticket-005

## Problem
Some pages require JavaScript rendering (SPAs, paywalled content behind soft walls, lazy-loaded content). When the validator detects poor extraction quality from the HTTP fetch, we need a Playwright fallback that renders the page in a headless browser.

## Requirements
- [x] Add `playwright` and `playwright-stealth` to `backend/pyproject.toml`
- [x] Create `backend/app/services/conversion/browser_fetcher.py`:
  - Async function `fetch_with_browser(url: str, timeout: int = 30) -> str` returning rendered HTML
  - Launch headless Chromium via Playwright
  - Apply stealth settings to avoid bot detection
  - Wait for network idle or DOM content loaded
  - Extract full page HTML after JS execution
  - Proper cleanup: always close browser context even on error
- [x] Integrate into `pipeline.py`:
  - After initial HTTP fetch + extraction, run validator
  - If validator fails (content too short, no title, etc.), retry with `browser_fetcher`
  - Set `ConversionResult.used_playwright = True` when fallback was used
  - If browser fetch also fails validation, raise a clear error
- [x] Add Playwright browser installation to setup instructions (or Dockerfile): `playwright install chromium`
- [x] Resource management: browser contexts should be short-lived (open per request, close after)

## Scope
- `backend/app/services/conversion/browser_fetcher.py` -- new file
- `backend/app/services/conversion/pipeline.py` -- modify to integrate fallback
- `backend/pyproject.toml` -- add playwright, playwright-stealth

## Notes
- Playwright is async-native, fits well with the async pipeline
- Browser fetch is expensive (memory, CPU, time) -- only use as fallback, never as default
- Consider a configurable flag to disable Playwright entirely (for environments without browser)
- Timeout for browser should be longer than HTTP timeout (30s vs 20s)
- Log when fallback is triggered with the validation failure reason
