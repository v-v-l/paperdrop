# kindle-send

Fetch web articles **with images preserved** and send them to your Kindle as EPUB.

Kindle's native "Share to Kindle" feature drops images. This tool keeps them — downloaded, optimized for e-ink, and embedded directly in the EPUB.

## How it works

```
URL → HTTP fetch → Mozilla Readability extraction → image download + optimize → EPUB → email to Kindle
```

No AI, no LLMs, no external APIs. Pure Python.

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Generate EPUB only
python kindle_send.py https://example.com/great-article

# Generate + send to Kindle
python kindle_send.py https://example.com/great-article --send

# First-time setup (SMTP + Kindle email)
python kindle_send.py --config

# Keep images in color (default converts to grayscale for e-ink)
python kindle_send.py https://example.com/article --keep-color

# Custom output directory
python kindle_send.py https://example.com/article -o ~/kindle-articles/
```

## Setup for sending

1. Run `python kindle_send.py --config`
2. Enter your SMTP settings (Gmail: `smtp.gmail.com`, port `587`, use an [App Password](https://support.google.com/accounts/answer/185833))
3. Enter your Kindle email (find it in Kindle app → Settings → Send-to-Kindle Email)
4. Add your sending email to [Amazon's approved list](https://www.amazon.com/hz/mycd/myx#/home/settings/payment)

## What it does

- **Extracts article content** using Mozilla's Readability algorithm (same as Firefox Reader View) — strips ads, navigation, sidebars, comments
- **Downloads all images**, resizes to 1200px max width, converts to grayscale JPEG for optimal e-ink rendering
- **Preserves metadata** — title, author, publication date, source URL
- **Builds a clean EPUB** with reader-friendly typography
- **Sends via email** to your Kindle's `@kindle.com` address

## Architecture

```
kindle_send.py          # Single-file tool, all-in-one
├── fetch_page()        # HTTP GET with browser User-Agent
├── extract_article()   # Readability + BeautifulSoup metadata extraction
├── process_images()    # Download, resize, grayscale, compress
├── build_epub()        # ebooklib EPUB assembly with CSS
└── send_to_kindle()    # SMTP email with EPUB attachment
```

## Limitations & future ideas

- **JS-heavy sites**: Currently uses plain HTTP requests. For SPAs and JS-rendered content, add Playwright as a fallback renderer:
  ```bash
  pip install playwright && playwright install chromium
  ```
- **Paywalled content**: Won't work behind logins (would need cookie/session support)
- **Very large articles**: EPUB must be under 50MB for Kindle's email gateway
- **Rate limiting**: No built-in delay between image downloads — some sites may throttle

## Dependencies

| Library | Purpose |
|---------|---------|
| `requests` | HTTP fetching |
| `readability-lxml` | Article extraction (Mozilla Readability) |
| `beautifulsoup4` | HTML parsing, image URL extraction |
| `lxml` | Fast HTML/XML parser backend |
| `ebooklib` | EPUB generation |
| `Pillow` | Image resizing, grayscale conversion, compression |

## License

MIT
