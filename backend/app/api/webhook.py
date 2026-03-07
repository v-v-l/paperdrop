"""Telegram webhook endpoint."""

from fastapi import APIRouter, Request, Response, status
from logs_flow import ErrorCodes, create_logger, format_error
from telegram import Update

from app.core.config import settings
from app.core.metrics import TELEGRAM_UPDATES_TOTAL

logger = create_logger(service="telegram-webhook")

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def telegram_webhook(request: Request) -> Response:
    """Receive Telegram updates via webhook.

    Verifies the webhook secret header before processing.
    Always returns 200 to acknowledge receipt (Telegram retries on non-200).
    """
    # Verify webhook secret
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if settings.TELEGRAM_WEBHOOK_SECRET and secret != settings.TELEGRAM_WEBHOOK_SECRET:
        logger.warning(
            "Webhook request with invalid secret",
            extra={"remote_addr": request.client.host if request.client else "unknown"},
        )
        return Response(status_code=status.HTTP_403_FORBIDDEN)

    # Parse the update
    try:
        data = await request.json()
        application = request.app.state.bot_application
        update = Update.de_json(data=data, bot=application.bot)

        # Track update type for metrics
        if update.message and update.message.text and update.message.text.startswith("/"):
            update_type = "command"
        elif update.pre_checkout_query or (
            update.message and update.message.successful_payment
        ):
            update_type = "payment"
        elif update.message:
            update_type = "message"
        else:
            update_type = "other"
        TELEGRAM_UPDATES_TOTAL.labels(update_type=update_type).inc()

        await application.process_update(update)
    except Exception as exc:
        logger.error(
            "Failed to process webhook update",
            extra=format_error(exc),
            error_code=ErrorCodes.INT_UNEXPECTED,
        )
        # Still return 200 to prevent Telegram from retrying
        return Response(status_code=status.HTTP_200_OK)

    return Response(status_code=status.HTTP_200_OK)
