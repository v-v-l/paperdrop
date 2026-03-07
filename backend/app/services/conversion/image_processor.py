"""Image downloading, resizing, and compression for EPUB embedding."""

import asyncio
import hashlib
import io
import urllib.parse
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup
from logs_flow import create_logger, format_error, ErrorCodes
from PIL import Image

logger = create_logger(service="conversion-images")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class ProcessedImage:
    filename: str
    data: bytes
    media_type: str


@dataclass
class ImageProcessingResult:
    content_html: str
    images: list[ProcessedImage]


def resolve_url(base_url: str, src: str) -> str:
    """Resolve relative/protocol-relative image URLs to absolute URLs."""
    if not src:
        return ""
    if src.startswith("data:"):
        return ""
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/"):
        parsed = urllib.parse.urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{src}"
    if not src.startswith("http"):
        return urllib.parse.urljoin(base_url, src)
    return src


def _optimize_image(
    raw_bytes: bytes,
    grayscale: bool,
    max_width: int,
    quality: int,
) -> tuple[bytes, str]:
    """Resize, optionally grayscale, and compress an image. Returns (bytes, extension).

    This function performs CPU-bound PIL operations and should be called
    via asyncio.to_thread().
    """
    img = Image.open(io.BytesIO(raw_bytes))

    # Convert to RGB (handles RGBA, P, etc.)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # Resize if too wide
    if img.width > max_width:
        ratio = max_width / img.width
        new_h = int(img.height * ratio)
        img = img.resize((max_width, new_h), Image.LANCZOS)

    if grayscale:
        img = img.convert("L")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue(), ".jpg"


async def download_and_optimize_image(
    url: str,
    client: httpx.AsyncClient,
    grayscale: bool = True,
    max_width: int = 1200,
    quality: int = 80,
    timeout: float = 20.0,
) -> tuple[bytes, str] | None:
    """Download an image and optimize it for e-reader display.

    Returns (optimized_bytes, extension) or None on failure.
    PIL operations run in a thread executor via asyncio.to_thread().
    """
    try:
        response = await client.get(
            url,
            timeout=httpx.Timeout(timeout),
            headers={"User-Agent": DEFAULT_USER_AGENT},
        )
        response.raise_for_status()

        optimized_bytes, ext = await asyncio.to_thread(
            _optimize_image, response.content, grayscale, max_width, quality
        )
        return optimized_bytes, ext

    except Exception as exc:
        logger.warning(
            "Failed to download/optimize image",
            extra={
                "url": url[:120],
                "error": format_error(exc),
                "error_code": ErrorCodes.API_UNAVAILABLE,
            },
        )
        return None


async def process_images(
    content_html: str,
    base_url: str,
    grayscale: bool = True,
    max_width: int = 1200,
    quality: int = 80,
    timeout: float = 20.0,
) -> ImageProcessingResult:
    """Find all images in HTML, download and optimize them, replace src with local refs.

    Args:
        content_html: HTML string with image tags.
        base_url: Base URL for resolving relative image paths.
        grayscale: Convert images to grayscale for e-readers.
        max_width: Maximum image width in pixels.
        quality: JPEG compression quality (1-100).
        timeout: Per-image download timeout in seconds.

    Returns:
        ImageProcessingResult with modified HTML and list of processed images.
    """
    soup = BeautifulSoup(content_html, "lxml")
    images: list[ProcessedImage] = []
    img_tags = soup.find_all("img")

    if img_tags:
        logger.info("Processing images", extra={"count": len(img_tags)})

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for i, img in enumerate(img_tags):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
            full_url = resolve_url(base_url, src)

            if not full_url:
                img.decompose()
                continue

            result = await download_and_optimize_image(
                full_url,
                client,
                grayscale=grayscale,
                max_width=max_width,
                quality=quality,
                timeout=timeout,
            )

            if result is None:
                img.decompose()
                continue

            img_bytes, ext = result
            img_hash = hashlib.md5(full_url.encode()).hexdigest()[:10]
            filename = f"img_{i:03d}_{img_hash}{ext}"

            img["src"] = filename
            # Remove srcset and lazy-loading attrs
            for attr in ["srcset", "data-src", "data-lazy-src", "loading"]:
                if attr in img.attrs:
                    del img.attrs[attr]

            images.append(ProcessedImage(
                filename=filename,
                data=img_bytes,
                media_type="image/jpeg",
            ))

            logger.debug(
                "Image processed",
                extra={
                    "index": i + 1,
                    "total": len(img_tags),
                    "size_kb": len(img_bytes) // 1024,
                },
            )

    logger.info(
        "Image processing complete",
        extra={
            "processed": len(images),
            "total_found": len(img_tags),
            "total_size_kb": sum(len(img.data) for img in images) // 1024,
        },
    )

    return ImageProcessingResult(
        content_html=str(soup),
        images=images,
    )
