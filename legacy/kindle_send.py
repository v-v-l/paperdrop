#!/usr/bin/env python3
"""
kindle-send: Fetch web articles with images and send to Kindle as EPUB.

Usage:
    python kindle_send.py <url>                          # Generate EPUB only
    python kindle_send.py <url> --send                   # Generate + send to Kindle
    python kindle_send.py <url> --kindle user@kindle.com # Set Kindle email
    python kindle_send.py --config                       # Configure SMTP + Kindle email

The pipeline:
    URL → HTTP fetch → Readability extraction → image download + compress → EPUB → email
"""

import argparse
import hashlib
import io
import json
import mimetypes
import os
import re
import smtplib
import sys
import time
import urllib.parse
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import warnings
warnings.filterwarnings("ignore", message="urllib3.*doesn't match a supported version")
import requests
from bs4 import BeautifulSoup
from ebooklib import epub
from PIL import Image
from readability import Document

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CONFIG_PATH = Path.home() / ".kindle_send" / "config.json"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
MAX_IMAGE_WIDTH = 1200  # px – good for Kindle e-ink
IMAGE_QUALITY = 80  # JPEG quality
MAX_EPUB_SIZE_MB = 48  # Kindle email limit ~50MB, leave margin
REQUEST_TIMEOUT = 20  # seconds


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {}


def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


def configure_interactive():
    """Interactive setup for SMTP and Kindle email."""
    cfg = load_config()
    print("=" * 50)
    print("  kindle-send configuration")
    print("=" * 50)
    print()
    print("SMTP settings (for sending emails to Kindle):")
    print("  Common: smtp.gmail.com (port 587)")
    print("  For Gmail, use an App Password, not your real password.")
    print()

    cfg["smtp_host"] = input(f"  SMTP host [{cfg.get('smtp_host', 'smtp.gmail.com')}]: ").strip() or cfg.get("smtp_host", "smtp.gmail.com")
    cfg["smtp_port"] = int(input(f"  SMTP port [{cfg.get('smtp_port', 587)}]: ").strip() or cfg.get("smtp_port", 587))
    cfg["smtp_user"] = input(f"  SMTP user (your email) [{cfg.get('smtp_user', '')}]: ").strip() or cfg.get("smtp_user", "")
    cfg["smtp_pass"] = input(f"  SMTP password/app-password: ").strip() or cfg.get("smtp_pass", "")
    cfg["from_email"] = cfg["smtp_user"]  # Usually same

    print()
    print("Kindle settings:")
    print("  Find your Kindle email in: Kindle app → Settings → Send-to-Kindle Email")
    print("  Make sure to approve the sender email in Amazon settings.")
    print()
    cfg["kindle_email"] = input(f"  Kindle email [{cfg.get('kindle_email', '')}]: ").strip() or cfg.get("kindle_email", "")

    save_config(cfg)
    print()
    print(f"Config saved to {CONFIG_PATH}")
    print("You can now run: kindle-send <url> --send")


# ---------------------------------------------------------------------------
# Fetch page
# ---------------------------------------------------------------------------
def fetch_page(url: str) -> str:
    """Fetch raw HTML from URL using requests."""
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    print(f"  Fetching {url}...")
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


# ---------------------------------------------------------------------------
# Extract article
# ---------------------------------------------------------------------------
def clean_title(title: str) -> str:
    """Strip site name suffixes like 'Article | Site' or 'Article — Site'."""
    for sep in [" | ", " \\ ", " — ", " – ", " - "]:
        if sep in title:
            parts = title.rsplit(sep, 1)
            title = max(parts, key=len).strip()
    return title


def extract_article(html: str, url: str) -> dict:
    """Use readability to extract clean article content."""
    doc = Document(html, url=url)
    title = clean_title(doc.title())
    content_html = doc.summary()

    # Also try to get author/date from meta tags
    soup = BeautifulSoup(html, "lxml")
    author = ""
    for meta in soup.find_all("meta"):
        name = meta.get("name", "").lower()
        prop = meta.get("property", "").lower()
        if name in ("author", "article:author") or prop in ("author", "article:author"):
            author = meta.get("content", "")
            break

    date = ""
    for meta in soup.find_all("meta"):
        name = meta.get("name", "").lower()
        prop = meta.get("property", "").lower()
        if name in ("date", "article:published_time", "publisheddate") or prop in (
            "article:published_time",
            "og:article:published_time",
        ):
            date = meta.get("content", "")
            break

    return {
        "title": title,
        "content_html": content_html,
        "author": author,
        "date": date,
        "source_url": url,
    }


# ---------------------------------------------------------------------------
# Process images
# ---------------------------------------------------------------------------
def resolve_url(base_url: str, src: str) -> str:
    """Resolve relative/protocol-relative image URLs."""
    if not src:
        return ""
    if src.startswith("data:"):
        return ""  # Skip data URIs for now
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/"):
        parsed = urllib.parse.urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{src}"
    if not src.startswith("http"):
        return urllib.parse.urljoin(base_url, src)
    return src


def download_and_optimize_image(url: str, grayscale: bool = True) -> tuple[bytes, str] | None:
    """Download image, resize, optionally grayscale, compress. Returns (bytes, ext)."""
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": DEFAULT_USER_AGENT})
        resp.raise_for_status()

        img = Image.open(io.BytesIO(resp.content))

        # Convert to RGB (handles RGBA, P, etc.)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        # Resize if too wide
        if img.width > MAX_IMAGE_WIDTH:
            ratio = MAX_IMAGE_WIDTH / img.width
            new_h = int(img.height * ratio)
            img = img.resize((MAX_IMAGE_WIDTH, new_h), Image.LANCZOS)

        if grayscale:
            img = img.convert("L")

        # Save as JPEG
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=IMAGE_QUALITY, optimize=True)
        return buf.getvalue(), ".jpg"

    except Exception as e:
        print(f"    ⚠ Failed to download image: {url[:80]}... ({e})")
        return None


def process_images(content_html: str, base_url: str, grayscale: bool = True) -> tuple[str, list[tuple[str, bytes, str]]]:
    """
    Find all images in HTML, download + optimize them, replace src with local refs.
    Returns (modified_html, [(filename, image_bytes, media_type), ...])
    """
    soup = BeautifulSoup(content_html, "lxml")
    images = []
    img_tags = soup.find_all("img")

    if img_tags:
        print(f"  Processing {len(img_tags)} images...")

    for i, img in enumerate(img_tags):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
        full_url = resolve_url(base_url, src)

        if not full_url:
            img.decompose()
            continue

        result = download_and_optimize_image(full_url, grayscale=grayscale)
        if result is None:
            img.decompose()
            continue

        img_bytes, ext = result
        # Create deterministic filename
        img_hash = hashlib.md5(full_url.encode()).hexdigest()[:10]
        filename = f"img_{i:03d}_{img_hash}{ext}"
        media_type = "image/jpeg"

        img["src"] = filename
        # Remove srcset and lazy-loading attrs
        for attr in ["srcset", "data-src", "data-lazy-src", "loading"]:
            if attr in img.attrs:
                del img.attrs[attr]

        images.append((filename, img_bytes, media_type))
        print(f"    ✓ Image {i+1}/{len(img_tags)}: {len(img_bytes)//1024}KB")

    return str(soup), images


# ---------------------------------------------------------------------------
# Build EPUB
# ---------------------------------------------------------------------------
def build_epub(article: dict, content_html: str, images: list, output_path: str) -> str:
    """Assemble EPUB file with article content and embedded images."""
    book = epub.EpubBook()

    # Metadata
    title = article["title"] or "Untitled Article"
    book.set_identifier(hashlib.md5(article["source_url"].encode()).hexdigest())
    book.set_title(title)
    book.set_language("en")
    if article["author"]:
        book.add_author(article["author"])
    book.add_metadata("DC", "source", article["source_url"])

    # Default CSS for clean Kindle reading
    css_content = """
    body {
        font-family: Georgia, serif;
        line-height: 1.6;
        margin: 1em;
        color: #000;
    }
    h1, h2, h3, h4 { margin-top: 1em; margin-bottom: 0.5em; }
    img {
        max-width: 100%;
        height: auto;
        display: block;
        margin: 1em auto;
    }
    p { margin: 0.5em 0; text-indent: 0; }
    blockquote {
        margin: 1em 2em;
        padding-left: 1em;
        border-left: 3px solid #666;
        font-style: italic;
    }
    a { color: #333; text-decoration: underline; }
    .source-info {
        font-size: 0.85em;
        color: #666;
        margin-bottom: 2em;
        border-bottom: 1px solid #ccc;
        padding-bottom: 1em;
    }
    """
    style = epub.EpubItem(
        uid="style",
        file_name="style/default.css",
        media_type="text/css",
        content=css_content.encode("utf-8"),
    )
    book.add_item(style)

    # Add images to book
    epub_images = []
    for filename, img_bytes, media_type in images:
        img_item = epub.EpubItem(
            uid=filename.replace(".", "_"),
            file_name=f"images/{filename}",
            media_type=media_type,
            content=img_bytes,
        )
        book.add_item(img_item)
        epub_images.append(img_item)

    # Fix image paths in HTML to point to images/ folder
    content_html = content_html.replace('src="img_', 'src="images/img_')

    # Build chapter HTML
    source_info = f'<div class="source-info">'
    if article["author"]:
        source_info += f'<strong>{article["author"]}</strong><br/>'
    if article["date"]:
        source_info += f'{article["date"]}<br/>'
    source_info += f'Source: {article["source_url"]}</div>'

    chapter = epub.EpubHtml(
        title=title,
        file_name="content.xhtml",
        lang="en",
    )
    chapter.content = f"""
    <html>
    <head><title>{title}</title></head>
    <body>
        <h1>{title}</h1>
        {source_info}
        {content_html}
    </body>
    </html>
    """
    chapter.add_item(style)
    book.add_item(chapter)

    # Table of contents & spine
    book.toc = [chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]

    # Write
    epub.write_epub(output_path, book)
    return output_path


# ---------------------------------------------------------------------------
# Send via email
# ---------------------------------------------------------------------------
def send_to_kindle(epub_path: str, cfg: dict):
    """Send EPUB as email attachment to Kindle."""
    if not all(cfg.get(k) for k in ("smtp_host", "smtp_user", "smtp_pass", "kindle_email")):
        print("  ✗ Missing SMTP or Kindle config. Run: kindle-send --config")
        sys.exit(1)

    file_size_mb = os.path.getsize(epub_path) / (1024 * 1024)
    if file_size_mb > MAX_EPUB_SIZE_MB:
        print(f"  ✗ EPUB too large ({file_size_mb:.1f}MB > {MAX_EPUB_SIZE_MB}MB limit)")
        sys.exit(1)

    filename = os.path.basename(epub_path)

    msg = MIMEMultipart()
    msg["From"] = cfg["from_email"]
    msg["To"] = cfg["kindle_email"]
    msg["Subject"] = "convert"  # Kindle magic subject for conversion

    msg.attach(MIMEText("Sent via kindle-send", "plain"))

    with open(epub_path, "rb") as f:
        part = MIMEBase("application", "epub+zip")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={filename}")
        msg.attach(part)

    print(f"  Sending to {cfg['kindle_email']}...")
    with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as server:
        server.starttls()
        server.login(cfg["smtp_user"], cfg["smtp_pass"])
        server.send_message(msg)
    print("  ✓ Sent!")


# ---------------------------------------------------------------------------
# Slugify title for filename
# ---------------------------------------------------------------------------
def slugify(text: str, max_len: int = 60) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:max_len].rstrip("-")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def process_url(url: str, output_dir: str = ".", send: bool = False, kindle_email: str = None, grayscale: bool = True):
    """Full pipeline: URL → EPUB (→ email)."""
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║              kindle-send                        ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    # 1. Fetch
    print("[1/4] Fetching page...")
    html = fetch_page(url)
    print(f"  ✓ Got {len(html)//1024}KB of HTML")

    # 2. Extract article
    print("[2/4] Extracting article...")
    article = extract_article(html, url)
    print(f'  ✓ Title: "{article["title"]}"')
    if article["author"]:
        print(f'  ✓ Author: {article["author"]}')

    # 3. Process images
    print("[3/4] Downloading images...")
    content_html, images = process_images(article["content_html"], url, grayscale=grayscale)
    total_img_kb = sum(len(b) for _, b, _ in images) // 1024
    print(f"  ✓ {len(images)} images downloaded ({total_img_kb}KB total)")

    # 4. Build EPUB
    print("[4/4] Building EPUB...")
    slug = slugify(article["title"]) or "article"
    epub_filename = f"{slug}.epub"
    epub_path = os.path.join(output_dir, epub_filename)
    build_epub(article, content_html, images, epub_path)
    epub_size = os.path.getsize(epub_path) / 1024
    print(f"  ✓ EPUB created: {epub_path} ({epub_size:.0f}KB)")

    # 5. Send (optional)
    if send:
        cfg = load_config()
        if kindle_email:
            cfg["kindle_email"] = kindle_email
        print()
        print("Sending to Kindle...")
        send_to_kindle(epub_path, cfg)

    print()
    print("Done! ✓")
    return epub_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Fetch web articles with images and send to Kindle as EPUB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  kindle-send https://example.com/article          # Just create EPUB
  kindle-send https://example.com/article --send    # Create + send to Kindle
  kindle-send --config                              # Set up SMTP + Kindle email
        """,
    )
    parser.add_argument("url", nargs="?", help="URL of the article to fetch")
    parser.add_argument("--send", action="store_true", help="Send EPUB to Kindle via email")
    parser.add_argument("--kindle", type=str, help="Override Kindle email address")
    parser.add_argument("--output", "-o", type=str, default=".", help="Output directory (default: current)")
    parser.add_argument("--config", action="store_true", help="Interactive configuration setup")
    parser.add_argument("--keep-color", action="store_true", help="Keep images in color (don't convert to grayscale)")

    args = parser.parse_args()

    if args.config:
        configure_interactive()
        return

    if not args.url:
        parser.print_help()
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)
    process_url(args.url, output_dir=args.output, send=args.send, kindle_email=args.kindle, grayscale=not args.keep_color)


if __name__ == "__main__":
    main()
