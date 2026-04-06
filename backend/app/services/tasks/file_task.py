"""ARQ task for EPUB/PDF/MD file processing."""

import os
import time

import httpx
from logs_flow import ErrorCodes, create_logger, format_error
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.core.config import settings
from app.core.db_resilience import (
    DB_ERRORS,
    generate_conversion_id,
    resilient_db_write,
)
from app.models.conversion import ConversionStatus
from app.models.user import User
from app.services.conversion.docx_converter import convert_docx_to_epub
from app.services.conversion.md_converter import convert_md_to_epub
from app.services.email.kindle_sender import send_to_kindle

logger = create_logger(service="file-task")


async def process_file(
    ctx: dict,
    user_id: int,
    chat_id: int,
    message_id: int,
    file_bytes: bytes,
    filename: str,
    file_type: str,
) -> None:
    """Process an EPUB, PDF, or Markdown file upload.

    Steps:
        1. Create Conversion record
        2. Convert to EPUB (external API for EPUB/PDF, local for MD)
        3. Send result EPUB via Telegram
        4. Send to Kindle if configured
        5. Update records, clean up
    """
    start_time = time.monotonic()
    session_factory = ctx["session_factory"]
    bot = ctx["bot"]
    redis = ctx["redis"]
    title = os.path.splitext(filename)[0]

    conversion_id = generate_conversion_id()

    logger.info(
        "File job started",
        extra={
            "user_id": user_id,
            "filename": filename,
            "file_type": file_type,
            "file_size_bytes": len(file_bytes),
        },
    )

    # 1. Create conversion record (resilient)
    await resilient_db_write(
        session_factory, redis,
        "create_conversion",
        {
            "id": conversion_id,
            "user_id": user_id,
            "url": f"file://{filename}",
            "title": title,
            "status": ConversionStatus.PROCESSING.value,
        },
    )

    epub_path: str | None = None

    try:
        # 2. Convert to EPUB
        if file_type == "md":
            md_text = file_bytes.decode("utf-8")
            output_dir = os.path.join(ctx["temp_dir"], f"file_{conversion_id}")
            os.makedirs(output_dir, exist_ok=True)
            local_epub_path = os.path.join(output_dir, f"{title}.epub")
            convert_md_to_epub(md_text, title, local_epub_path)
            with open(local_epub_path, "rb") as f:
                epub_bytes = f.read()
        elif file_type == "docx":
            output_dir = os.path.join(ctx["temp_dir"], f"file_{conversion_id}")
            os.makedirs(output_dir, exist_ok=True)
            local_epub_path = os.path.join(output_dir, f"{title}.epub")
            convert_docx_to_epub(file_bytes, title, local_epub_path)
            with open(local_epub_path, "rb") as f:
                epub_bytes = f.read()
        else:
            if file_type == "epub":
                api_url = settings.EPUB_FIXER_URL
                mime = "application/epub+zip"
            else:
                api_url = settings.PDF_TO_EPUB_URL
                mime = "application/pdf"

            headers = {}
            if file_type == "epub" and settings.EPUB_API_KEY:
                headers["X-API-Key"] = settings.EPUB_API_KEY

            async with httpx.AsyncClient(timeout=120.0) as client:
                files = {"file": (filename, file_bytes, mime)}
                data = {"mode": "reflow", "author": "Unknown"} if file_type == "pdf" else None
                response = await client.post(api_url, files=files, data=data, headers=headers)
                response.raise_for_status()
                epub_bytes = response.content

        # 3. Save to temp file
        output_dir = os.path.join(ctx["temp_dir"], f"file_{conversion_id}")
        os.makedirs(output_dir, exist_ok=True)
        output_filename = f"{title}.epub"
        epub_path = os.path.join(output_dir, output_filename)
        with open(epub_path, "wb") as f:
            f.write(epub_bytes)

        file_size = len(epub_bytes)

        # 4. Update conversion record (resilient)
        await resilient_db_write(
            session_factory, redis,
            "update_conversion",
            {
                "id": conversion_id,
                "title": title,
                "file_size_bytes": file_size,
                "status": ConversionStatus.COMPLETED.value,
            },
        )
        await resilient_db_write(
            session_factory, redis,
            "increment_user_conversions",
            {"user_id": user_id},
        )

        # 5. Send EPUB via Telegram
        with open(epub_path, "rb") as epub_file:
            await bot.send_document(
                chat_id=chat_id,
                document=epub_file,
                filename=output_filename,
                reply_to_message_id=message_id,
            )

        # 6. Send to Kindle if configured
        kindle_email = None
        user_result = None
        try:
            async with session_factory() as session:
                user_result = await session.get(User, user_id)
                kindle_email = user_result.kindle_email if user_result else None
        except DB_ERRORS:
            logger.warning("DB unavailable for Kindle lookup, skipping delivery")

        if kindle_email:
            sent = await send_to_kindle(
                kindle_email=kindle_email,
                epub_path=epub_path,
                title=title,
            )
            kindle_status = "success" if sent else "failed"
            await resilient_db_write(
                session_factory, redis,
                "update_conversion",
                {"id": conversion_id, "kindle_status": kindle_status},
            )
            if sent:
                status_text = f"Delivered to Kindle ({kindle_email})"
            else:
                status_text = (
                    f"Failed to deliver to Kindle ({kindle_email}). "
                    "The EPUB is available above — you can forward it manually."
                )
                logger.warning(
                    "Kindle delivery failed",
                    extra={"user_id": user_id, "kindle_email": kindle_email},
                )
            await bot.send_message(
                chat_id=chat_id,
                text=status_text,
                reply_to_message_id=message_id,
            )
        elif user_result and user_result.total_conversions <= 3:
            hint = (
                "Want this on your Kindle? It's a one-time setup:\n\n"
                "1. Open amazon.com/sendtokindle — find your Kindle email\n"
                f"2. Add {settings.SENDER_EMAIL} to your Approved Senders (same page)\n"
                "3. Paste your Kindle email below"
            )
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Set up Kindle",
                    web_app=WebAppInfo(url=settings.MINI_APP_URL),
                )
            ]])
            await bot.send_message(
                chat_id=chat_id,
                text=hint,
                reply_markup=keyboard,
                reply_to_message_id=message_id,
            )

        elapsed = time.monotonic() - start_time
        logger.info(
            "File job completed",
            extra={
                "conversion_id": conversion_id,
                "user_id": user_id,
                "filename": filename,
                "file_type": file_type,
                "file_size_bytes": file_size,
                "elapsed_seconds": round(elapsed, 2),
            },
        )

    except Exception as exc:
        elapsed = time.monotonic() - start_time
        error_msg = str(exc)[:500]

        logger.error(
            "File job failed",
            extra={
                "conversion_id": conversion_id,
                "user_id": user_id,
                "filename": filename,
                "file_type": file_type,
                "elapsed_seconds": round(elapsed, 2),
                **format_error(exc),
            },
            error_code=ErrorCodes.INT_UNEXPECTED,
        )

        await resilient_db_write(
            session_factory, redis,
            "update_conversion",
            {
                "id": conversion_id,
                "status": ConversionStatus.FAILED.value,
                "error_message": error_msg,
            },
        )

        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"Failed to process your file. Please try again later.\n\nError: {error_msg}",
                reply_to_message_id=message_id,
            )
        except Exception as notify_exc:
            logger.error(
                "Failed to send error notification",
                extra={"chat_id": chat_id, **format_error(notify_exc)},
                error_code=ErrorCodes.API_UNAVAILABLE,
            )

    finally:
        if epub_path and os.path.exists(epub_path):
            try:
                os.remove(epub_path)
                output_dir = os.path.dirname(epub_path)
                if os.path.isdir(output_dir) and not os.listdir(output_dir):
                    os.rmdir(output_dir)
            except OSError as cleanup_exc:
                logger.warning(
                    "Failed to delete temp file",
                    extra={"epub_path": epub_path, **format_error(cleanup_exc)},
                )
