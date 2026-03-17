"""Telegram bot command and message handlers."""

import time
from datetime import datetime, timezone

from arq import create_pool
from arq.connections import RedisSettings
from logs_flow import ErrorCodes, create_logger, format_error
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update, WebAppInfo
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.metrics import (
    ACTIVE_SUBSCRIPTIONS,
    BOT_COMMANDS_TOTAL,
    BOT_NEW_USERS_TOTAL,
    FREE_TIER_LIMIT_HITS_TOTAL,
    RATE_LIMIT_HITS_TOTAL,
)
from app.i18n import get_text
from app.models.conversion import Conversion, ConversionStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
from app.services.payments.subscription_service import (
    can_convert,
    check_subscription,
    create_subscription,
)
from app.services.rate_limiter import check_rate_limit
from app.services.tasks import enqueue_conversion, enqueue_file
from app.services.telegram.url_utils import extract_urls, is_valid_url

logger = create_logger(service="telegram-handlers")


def _locale(update: Update) -> str | None:
    """Extract the user's language_code from the Telegram update."""
    if update.effective_user:
        return update.effective_user.language_code
    return None


def _t(update: Update, key: str, **kwargs: object) -> str:
    """Shorthand for bot module translations using the user's locale."""
    return get_text(_locale(update), "bot", key, **kwargs)


async def _get_or_create_user(
    session: AsyncSession, update: Update
) -> User:
    """Get or create a User record from a Telegram update.

    Uses the Telegram user ID as the primary key. Updates username,
    first_name, and language_code on every interaction.
    """
    tg_user = update.effective_user
    if tg_user is None:
        raise ValueError("Update has no effective_user")

    user = await session.get(User, tg_user.id)
    if user is None:
        user = User(
            id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            language_code=tg_user.language_code,
        )
        session.add(user)
        BOT_NEW_USERS_TOTAL.inc()
    else:
        # Update profile fields on each interaction
        user.username = tg_user.username
        user.first_name = tg_user.first_name
        user.language_code = tg_user.language_code

    await session.commit()
    await session.refresh(user)
    return user


def _has_active_subscription(user: User) -> bool:
    """Check if the user has an active, non-expired subscription."""
    sub = user.subscription
    if sub is None:
        return False
    if sub.status != SubscriptionStatus.ACTIVE.value:
        return False
    now = datetime.now(timezone.utc)
    if sub.current_period_end and sub.current_period_end < now:
        return False
    return True


def _can_convert(user: User) -> bool:
    """Check if the user is allowed to enqueue a new conversion."""
    if _has_active_subscription(user):
        return True
    return user.total_conversions < settings.FREE_TIER_LIMIT


async def _get_redis_pool():
    """Create an ARQ Redis connection pool."""
    from urllib.parse import urlparse

    parsed = urlparse(settings.REDIS_URL)
    redis_settings = RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or 0),
        password=parsed.password,
    )
    return await create_pool(redis_settings)


# -- Command Handlers --


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command: welcome message and upsert user."""
    BOT_COMMANDS_TOTAL.labels(command="start").inc()
    async with async_session_factory() as session:
        await _get_or_create_user(session, update)

    await update.message.reply_text(_t(update, "welcome"))

    logger.info(
        "User started bot",
        extra={"user_id": update.effective_user.id},
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command: usage instructions, privacy info, disclaimer."""
    BOT_COMMANDS_TOTAL.labels(command="help").inc()
    await update.message.reply_text(_t(update, "help"))


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings command: inline button that opens the Mini App."""
    BOT_COMMANDS_TOTAL.labels(command="settings").inc()
    mini_app_url = settings.MINI_APP_URL
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=_t(update, "settings_button"),
                    web_app=WebAppInfo(url=mini_app_url),
                )
            ]
        ]
    )
    await update.message.reply_text(
        _t(update, "settings_message"),
        reply_markup=keyboard,
    )


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /history command: show last 10 conversions."""
    BOT_COMMANDS_TOTAL.labels(command="history").inc()
    async with async_session_factory() as session:
        user = await _get_or_create_user(session, update)

        result = await session.execute(
            select(Conversion)
            .where(Conversion.user_id == user.id)
            .order_by(Conversion.created_at.desc())
            .limit(10)
        )
        conversions = result.scalars().all()

    if not conversions:
        await update.message.reply_text(_t(update, "history_empty"))
        return

    lines = [_t(update, "history_header"), ""]
    for conv in conversions:
        title = conv.title or conv.url[:40]
        status_icon = {
            ConversionStatus.PENDING.value: "...",
            ConversionStatus.PROCESSING.value: "...",
            ConversionStatus.COMPLETED.value: "OK",
            ConversionStatus.FAILED.value: "FAIL",
        }.get(conv.status, "?")
        date_str = conv.created_at.strftime("%Y-%m-%d") if conv.created_at else "?"
        lines.append(f"[{status_icon}] {title} ({date_str})")

    await update.message.reply_text("\n".join(lines))


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /subscribe command: send Stripe invoice or show active subscription."""
    BOT_COMMANDS_TOTAL.labels(command="subscribe").inc()
    async with async_session_factory() as session:
        user = await _get_or_create_user(session, update)
        is_subscribed = await check_subscription(session, user.id)

    if is_subscribed:
        sub = user.subscription
        end_str = sub.current_period_end.strftime("%Y-%m-%d") if sub.current_period_end else "?"
        await update.message.reply_text(
            _t(update, "subscribe_already_active", end=end_str)
        )
        return

    payload = f"sub_{user.id}_{int(time.time())}"
    prices = [LabeledPrice("PaperDrop Pro (30 days)", settings.SUBSCRIPTION_PRICE_STARS)]

    await update.message.reply_invoice(
        title=_t(update, "subscribe_invoice_title"),
        description=_t(update, "subscribe_invoice_description"),
        payload=payload,
        provider_token="",  # Empty string = Telegram Stars
        currency="XTR",  # XTR = Telegram Stars currency
        prices=prices,
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command: show subscription status and remaining conversions."""
    BOT_COMMANDS_TOTAL.labels(command="status").inc()
    async with async_session_factory() as session:
        user = await _get_or_create_user(session, update)

    if _has_active_subscription(user):
        sub = user.subscription
        start_str = sub.current_period_start.strftime("%Y-%m-%d") if sub.current_period_start else "?"
        end_str = sub.current_period_end.strftime("%Y-%m-%d") if sub.current_period_end else "?"
        text = _t(
            update, "status_subscribed",
            status=sub.status.capitalize(),
            start=start_str,
            end=end_str,
        )
    else:
        used = user.total_conversions
        limit = settings.FREE_TIER_LIMIT
        remaining = max(0, limit - used)

        if remaining > 0:
            text = _t(
                update, "status_free",
                used=used,
                limit=limit,
                remaining=remaining,
            )
        else:
            text = _t(
                update, "status_free_exhausted",
                used=used,
                limit=limit,
            )

    await update.message.reply_text(text)


# -- Message Handlers --


async def url_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text messages: detect URLs, validate, check limits, enqueue conversion."""
    message = update.message
    if not message or not message.text:
        return

    # Extract and validate URLs
    raw_urls = extract_urls(message.text)
    valid_urls = [url for url in raw_urls if is_valid_url(url)]

    if not raw_urls:
        # No URLs found at all -- ignore the message (don't spam the user)
        return

    if not valid_urls:
        await message.reply_text(_t(update, "invalid_url"))
        return

    # Ensure user exists and check conversion eligibility
    async with async_session_factory() as session:
        user = await _get_or_create_user(session, update)

    # Check per-user rate limit (before free tier / subscription check)
    try:
        redis = await _get_redis_pool()
    except Exception as exc:
        logger.error(
            "Failed to connect to Redis",
            extra={"user_id": user.id, **format_error(exc)},
            error_code=ErrorCodes.INT_UNEXPECTED,
        )
        await message.reply_text(_t(update, "error_generic"))
        return

    try:
        is_paid = _has_active_subscription(user)
        if is_paid:
            max_requests = settings.RATE_LIMIT_PAID_MAX
            window_seconds = settings.RATE_LIMIT_PAID_WINDOW
        else:
            max_requests = settings.RATE_LIMIT_FREE_MAX
            window_seconds = settings.RATE_LIMIT_FREE_WINDOW

        rate_allowed, seconds_until_reset = await check_rate_limit(
            redis=redis,
            user_id=user.id,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )

        if not rate_allowed:
            tier = "paid" if is_paid else "free"
            RATE_LIMIT_HITS_TOTAL.labels(tier=tier).inc()
            minutes = max(1, seconds_until_reset // 60)
            plural = "s" if minutes != 1 else ""
            await message.reply_text(
                _t(update, "rate_limited", minutes=minutes, plural=plural)
            )
            return

        # Check free tier / subscription eligibility
        async with async_session_factory() as session:
            allowed, reason = await can_convert(session, user.id)

        if not allowed:
            FREE_TIER_LIMIT_HITS_TOTAL.inc()
            await message.reply_text(
                _t(update, "free_limit_reached", limit=settings.FREE_TIER_LIMIT)
            )
            return

        # Send acknowledgment
        if len(valid_urls) == 1:
            ack = await message.reply_text(_t(update, "processing"))
        else:
            ack = await message.reply_text(
                _t(update, "processing_multiple", count=len(valid_urls))
            )

        # Enqueue conversion jobs
        for url in valid_urls:
            await enqueue_conversion(
                redis=redis,
                user_id=user.id,
                url=url,
                chat_id=message.chat_id,
                message_id=message.message_id,
                grayscale=user.grayscale_images,
            )
    except Exception as exc:
        logger.error(
            "Failed to enqueue conversion",
            extra={
                "user_id": user.id,
                "urls": valid_urls,
                **format_error(exc),
            },
            error_code=ErrorCodes.INT_UNEXPECTED,
        )
        await message.reply_text(_t(update, "error_generic"))
        return
    finally:
        await redis.close()

    logger.info(
        "Conversions enqueued",
        extra={
            "user_id": user.id,
            "url_count": len(valid_urls),
            "urls": valid_urls,
        },
    )


# -- Document Handlers --


def _validate_epub(file_bytes: bytes) -> str | None:
    """Validate EPUB file. Returns error i18n key or None if valid."""
    import io
    import zipfile

    if not zipfile.is_zipfile(io.BytesIO(file_bytes)):
        return "epub_invalid_format"

    with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as zf:
        names = zf.namelist()
        if "mimetype" not in names:
            return "epub_invalid_format"

        if "META-INF/encryption.xml" in names:
            encryption_xml = zf.read("META-INF/encryption.xml").decode("utf-8", errors="ignore")
            if "EncryptedData" in encryption_xml:
                return "epub_drm_protected"

    return None


def _extract_epub_from_zip(file_bytes: bytes) -> bytes | None:
    """Extract an EPUB from a ZIP that contains an exploded .epub folder.

    macOS often treats EPUBs as folders. When users zip them, the result
    is a ZIP with a nested `book.epub/` directory containing the EPUB files.
    This function repacks that into a proper EPUB (ZIP with mimetype at root).

    Returns repacked EPUB bytes, or None if no valid EPUB folder found.
    """
    import io
    import zipfile

    if not zipfile.is_zipfile(io.BytesIO(file_bytes)):
        return None

    with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as outer_zip:
        names = outer_zip.namelist()

        # Find .epub/ directory entries (skip __MACOSX)
        epub_dirs = [
            n for n in names
            if n.endswith(".epub/") and not n.startswith("__MACOSX")
        ]
        if not epub_dirs:
            return None

        prefix = epub_dirs[0]

        # Verify it has mimetype inside
        if prefix + "mimetype" not in names:
            return None

        # Repack: strip the prefix, skip __MACOSX, write proper EPUB
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as epub_zip:
            # mimetype must be first and uncompressed per EPUB spec
            epub_zip.writestr(
                "mimetype",
                outer_zip.read(prefix + "mimetype"),
                compress_type=zipfile.ZIP_STORED,
            )

            for entry in names:
                if entry.startswith("__MACOSX"):
                    continue
                if not entry.startswith(prefix):
                    continue
                if entry == prefix or entry == prefix + "mimetype":
                    continue  # skip directory entry and already-written mimetype

                relative_path = entry[len(prefix):]
                if not relative_path:
                    continue

                epub_zip.writestr(relative_path, outer_zip.read(entry))

        return output.getvalue()


def _validate_pdf(file_bytes: bytes) -> str | None:
    """Validate PDF file. Returns error i18n key or None if valid."""
    if not file_bytes[:5] == b"%PDF-":
        return "pdf_invalid_format"
    return None


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle EPUB and PDF file attachments."""
    message = update.message
    if not message or not message.document:
        return

    doc = message.document
    filename = doc.file_name or "file"
    lower_name = filename.lower()

    # Determine file type
    if lower_name.endswith(".epub") or doc.mime_type == "application/epub+zip":
        file_type = "epub"
    elif lower_name.endswith(".pdf") or doc.mime_type == "application/pdf":
        file_type = "pdf"
    elif lower_name.endswith(".zip") or doc.mime_type in ("application/zip", "application/x-zip-compressed"):
        file_type = "zip"
    else:
        return

    # Check file size limit
    if doc.file_size and doc.file_size > settings.TELEGRAM_MAX_FILE_SIZE:
        await message.reply_text(_t(update, "file_too_big"))
        return

    # Ensure user exists
    async with async_session_factory() as session:
        user = await _get_or_create_user(session, update)

    # Rate limit + eligibility checks (same as URL handler)
    try:
        redis = await _get_redis_pool()
    except Exception as exc:
        logger.error(
            "Failed to connect to Redis",
            extra={"user_id": user.id, **format_error(exc)},
            error_code=ErrorCodes.INT_UNEXPECTED,
        )
        await message.reply_text(_t(update, "error_generic"))
        return

    try:
        is_paid = _has_active_subscription(user)
        max_requests = settings.RATE_LIMIT_PAID_MAX if is_paid else settings.RATE_LIMIT_FREE_MAX
        window_seconds = settings.RATE_LIMIT_PAID_WINDOW if is_paid else settings.RATE_LIMIT_FREE_WINDOW

        rate_allowed, seconds_until_reset = await check_rate_limit(
            redis=redis, user_id=user.id,
            max_requests=max_requests, window_seconds=window_seconds,
        )
        if not rate_allowed:
            tier = "paid" if is_paid else "free"
            RATE_LIMIT_HITS_TOTAL.labels(tier=tier).inc()
            minutes = max(1, seconds_until_reset // 60)
            plural = "s" if minutes != 1 else ""
            await message.reply_text(_t(update, "rate_limited", minutes=minutes, plural=plural))
            return

        async with async_session_factory() as session:
            allowed, reason = await can_convert(session, user.id)
        if not allowed:
            FREE_TIER_LIMIT_HITS_TOTAL.inc()
            await message.reply_text(_t(update, "free_limit_reached", limit=settings.FREE_TIER_LIMIT))
            return

        # Download file from Telegram
        try:
            tg_file = await doc.get_file()
        except BadRequest as exc:
            if "file is too big" in str(exc).lower():
                await message.reply_text(_t(update, "file_too_big"))
                return
            raise
        file_bytes = bytes(await tg_file.download_as_bytearray())

        # ZIP: check if it's an EPUB (renamed or containing an .epub folder)
        if file_type == "zip":
            epub_check = _validate_epub(file_bytes)
            if epub_check is None:
                # It's a valid EPUB packaged as .zip
                file_type = "epub"
                filename = filename.rsplit(".", 1)[0] + ".epub"
            else:
                # Try extracting a nested .epub folder (macOS-zipped EPUB)
                repacked = _extract_epub_from_zip(file_bytes)
                if repacked is not None:
                    file_bytes = repacked
                    file_type = "epub"
                    filename = filename.rsplit(".", 1)[0] + ".epub"
                else:
                    await message.reply_text(_t(update, "zip_not_epub"))
                    return

        # Validate
        if file_type == "epub":
            error_key = _validate_epub(file_bytes)
        elif file_type == "pdf":
            error_key = _validate_pdf(file_bytes)
        else:
            return

        if error_key:
            await message.reply_text(_t(update, error_key))
            return

        # Acknowledge
        ack_key = "file_processing_epub" if file_type == "epub" else "file_processing_pdf"
        await message.reply_text(_t(update, ack_key))

        # Enqueue
        await enqueue_file(
            redis=redis,
            user_id=user.id,
            chat_id=message.chat_id,
            message_id=message.message_id,
            file_bytes=file_bytes,
            filename=filename,
            file_type=file_type,
        )
    except Exception as exc:
        logger.error(
            "Failed to process file upload",
            extra={"user_id": user.id, "filename": filename, **format_error(exc)},
            error_code=ErrorCodes.INT_UNEXPECTED,
        )
        await message.reply_text(_t(update, "error_generic"))
        return
    finally:
        await redis.close()

    logger.info(
        "File enqueued",
        extra={"user_id": user.id, "filename": filename, "file_type": file_type},
    )


# -- Payment Handlers --


async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pre_checkout_query: validate and approve the payment."""
    query = update.pre_checkout_query
    if query is None:
        return

    # For MVP we approve all pre-checkout queries. Telegram requires a
    # response within 10 seconds.
    await query.answer(ok=True)

    logger.info(
        "Pre-checkout approved",
        extra={
            "user_id": query.from_user.id,
            "invoice_payload": query.invoice_payload,
            "total_amount": query.total_amount,
            "currency": query.currency,
        },
    )


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle successful_payment: create subscription and notify user."""
    message = update.message
    if message is None or message.successful_payment is None:
        return

    payment = message.successful_payment
    user_id = message.from_user.id

    try:
        async with async_session_factory() as session:
            subscription = await create_subscription(
                db=session,
                user_id=user_id,
                charge_id=payment.telegram_payment_charge_id,
                provider_charge_id=payment.provider_payment_charge_id,
            )

        start_str = subscription.current_period_start.strftime("%Y-%m-%d")
        end_str = subscription.current_period_end.strftime("%Y-%m-%d")

        ACTIVE_SUBSCRIPTIONS.inc()
        await message.reply_text(
            _t(update, "payment_success", start=start_str, end=end_str)
        )

        logger.info(
            "Payment successful, subscription created",
            extra={
                "user_id": user_id,
                "subscription_id": subscription.id,
                "charge_id": payment.telegram_payment_charge_id,
                "provider_charge_id": payment.provider_payment_charge_id,
                "amount": payment.total_amount,
                "currency": payment.currency,
            },
        )
    except Exception as exc:
        logger.error(
            "Failed to create subscription after payment",
            extra={
                "user_id": user_id,
                "charge_id": payment.telegram_payment_charge_id,
                **format_error(exc),
            },
            error_code=ErrorCodes.INT_UNEXPECTED,
        )
        await message.reply_text(_t(update, "payment_error"))
