"""Send EPUB files to Kindle via Resend email API."""

import base64
import os

import httpx
from logs_flow import ErrorCodes, create_logger, format_error

from app.core.config import settings

logger = create_logger(service="kindle-sender")

RESEND_API_URL = "https://api.resend.com/emails"


async def send_to_kindle(
    kindle_email: str,
    epub_path: str,
    title: str,
) -> bool:
    """Send an EPUB file to a Kindle email address via Resend.

    Args:
        kindle_email: The user's @kindle.com address.
        epub_path: Path to the EPUB file on disk.
        title: Article title (used in subject line and filename).

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured, skipping Kindle delivery")
        return False

    filename = f"{title or 'article'}.epub"

    with open(epub_path, "rb") as f:
        file_content = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "from": settings.SENDER_EMAIL,
        "to": [kindle_email],
        "subject": title or "Your article from PaperDrop",
        "text": f"Here is your article: {title}",
        "attachments": [
            {
                "filename": filename,
                "content": file_content,
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                RESEND_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()

        logger.info(
            "Kindle email sent",
            extra={
                "kindle_email": kindle_email,
                "filename": filename,
                "file_size_bytes": os.path.getsize(epub_path),
            },
        )
        return True

    except Exception as exc:
        logger.error(
            "Failed to send Kindle email",
            extra={
                "kindle_email": kindle_email,
                "filename": filename,
                **format_error(exc),
            },
            error_code=ErrorCodes.API_UNAVAILABLE,
        )
        return False
