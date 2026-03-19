"""ARQ task for URL-to-EPUB conversion."""

import os
import time

from logs_flow import ErrorCodes, create_logger, format_error
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.core.config import settings
from app.core.metrics import (
    ACTIVE_CONVERSIONS,
    CONVERSION_DURATION_SECONDS,
    CONVERSIONS_TOTAL,
)
from app.models.conversion import Conversion, ConversionStatus
from app.models.user import User
from app.services.conversion import convert_url
from app.services.email.kindle_sender import send_to_kindle

logger = create_logger(service="conversion-task")


async def process_conversion(
    ctx: dict,
    user_id: int,
    url: str,
    chat_id: int,
    message_id: int,
    grayscale: bool = True,
) -> None:
    """Process a URL-to-EPUB conversion job.

    Steps:
        1. Create Conversion record with status 'processing'
        2. Run convert_url() pipeline
        3. On success: update record, increment user conversions, send EPUB via Telegram
        4. On failure: update record to 'failed', notify user via Telegram
        5. Always delete temp EPUB file after sending
    """
    start_time = time.monotonic()
    session_factory = ctx["session_factory"]
    bot = ctx["bot"]

    logger.info(
        "Job started",
        extra={"user_id": user_id, "url": url, "chat_id": chat_id},
    )

    async with session_factory() as session:
        session: AsyncSession

        # 1. Create conversion record
        conversion = Conversion(
            user_id=user_id,
            url=url,
            status=ConversionStatus.PROCESSING.value,
        )
        session.add(conversion)
        await session.commit()
        await session.refresh(conversion)
        conversion_id = conversion.id

    epub_path: str | None = None
    ACTIVE_CONVERSIONS.inc()

    try:
        # 2. Run pipeline
        output_dir = os.path.join(ctx["temp_dir"], f"conv_{conversion_id}")
        result = await convert_url(url=url, output_dir=output_dir, grayscale=grayscale)
        epub_path = result.epub_path

        # 3. Update conversion record on success
        async with session_factory() as session:
            await session.execute(
                update(Conversion)
                .where(Conversion.id == conversion_id)
                .values(
                    title=result.title,
                    author=result.author,
                    file_size_bytes=result.file_size_bytes,
                    image_count=result.image_count,
                    used_playwright=result.used_playwright,
                    status=ConversionStatus.COMPLETED.value,
                )
            )
            # Atomically increment total_conversions
            await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(total_conversions=User.total_conversions + 1)
            )
            await session.commit()

        # 4. Send EPUB via Telegram
        filename = f"{result.title or 'article'}.epub"
        with open(epub_path, "rb") as epub_file:
            await bot.send_document(
                chat_id=chat_id,
                document=epub_file,
                filename=filename,
                reply_to_message_id=message_id,
            )

        # 5. Send to Kindle if user has kindle_email configured
        async with session_factory() as session:
            user_result = await session.get(User, user_id)
            kindle_email = user_result.kindle_email if user_result else None

        if kindle_email:
            sent = await send_to_kindle(
                kindle_email=kindle_email,
                epub_path=epub_path,
                title=result.title or "article",
            )
            kindle_status = "success" if sent else "failed"
            async with session_factory() as session:
                await session.execute(
                    update(Conversion)
                    .where(Conversion.id == conversion_id)
                    .values(kindle_status=kindle_status)
                )
                await session.commit()
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
        CONVERSIONS_TOTAL.labels(status="completed", source_type="url").inc()
        CONVERSION_DURATION_SECONDS.labels(source_type="url").observe(elapsed)
        logger.info(
            "Job completed",
            extra={
                "conversion_id": conversion_id,
                "user_id": user_id,
                "url": url,
                "title": result.title,
                "file_size_bytes": result.file_size_bytes,
                "elapsed_seconds": round(elapsed, 2),
            },
        )

    except Exception as exc:
        elapsed = time.monotonic() - start_time
        CONVERSIONS_TOTAL.labels(status="failed", source_type="url").inc()
        CONVERSION_DURATION_SECONDS.labels(source_type="url").observe(elapsed)
        error_msg = str(exc)[:500]

        logger.error(
            "Job failed",
            extra={
                "conversion_id": conversion_id,
                "user_id": user_id,
                "url": url,
                "elapsed_seconds": round(elapsed, 2),
                **format_error(exc),
            },
            error_code=ErrorCodes.INT_UNEXPECTED,
        )

        # Update conversion to failed
        async with session_factory() as session:
            await session.execute(
                update(Conversion)
                .where(Conversion.id == conversion_id)
                .values(
                    status=ConversionStatus.FAILED.value,
                    error_message=error_msg,
                )
            )
            await session.commit()

        # Notify user of failure
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"Failed to convert the link. Please try again later.\n\nError: {error_msg}",
                reply_to_message_id=message_id,
            )
        except Exception as notify_exc:
            logger.error(
                "Failed to send error notification to user",
                extra={
                    "chat_id": chat_id,
                    "user_id": user_id,
                    **format_error(notify_exc),
                },
                error_code=ErrorCodes.API_UNAVAILABLE,
            )

    finally:
        ACTIVE_CONVERSIONS.dec()
        # 6. Delete temp file (privacy-first)
        if epub_path and os.path.exists(epub_path):
            try:
                os.remove(epub_path)
                # Also remove the output directory if empty
                output_dir = os.path.dirname(epub_path)
                if os.path.isdir(output_dir) and not os.listdir(output_dir):
                    os.rmdir(output_dir)
            except OSError as cleanup_exc:
                logger.warning(
                    "Failed to delete temp file",
                    extra={"epub_path": epub_path, **format_error(cleanup_exc)},
                )
