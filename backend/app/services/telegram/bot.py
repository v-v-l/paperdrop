"""Telegram bot Application initialization and lifecycle management."""

from logs_flow import ErrorCodes, create_logger, format_error
from telegram import Bot, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, PreCheckoutQueryHandler, filters
from telegram.request import HTTPXRequest

from app.core.config import settings
from app.services.telegram.handlers import (
    document_handler,
    help_command,
    history_command,
    pre_checkout_handler,
    settings_command,
    start_command,
    status_command,
    subscribe_command,
    successful_payment_handler,
    url_message_handler,
)

logger = create_logger(service="telegram-bot")


def create_bot_application() -> Application:
    """Create and configure the python-telegram-bot Application.

    The application is configured for webhook mode (no built-in updater).
    All command and message handlers are registered here.

    Returns:
        Configured Application instance.
    """
    request = HTTPXRequest(
        read_timeout=30,
        write_timeout=30,
        connect_timeout=10,
    )
    builder = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .base_url(settings.TELEGRAM_API_BASE_URL)
        .base_file_url(settings.TELEGRAM_API_BASE_FILE_URL)
        .local_mode(settings.TELEGRAM_LOCAL_MODE)
        .request(request)
        .updater(None)  # Webhook mode: no polling updater
    )
    application = builder.build()

    # Register command handlers (priority: commands first)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("status", status_command))

    # Register payment handlers (must be before generic message handlers)
    application.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    application.add_handler(
        MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler)
    )

    # Register document handler for EPUB/PDF/MD/ZIP files
    epub_filter = filters.Document.MimeType("application/epub+zip") | filters.Document.FileExtension("epub")
    pdf_filter = filters.Document.MimeType("application/pdf") | filters.Document.FileExtension("pdf")
    md_filter = filters.Document.MimeType("text/markdown") | filters.Document.FileExtension("md")
    docx_filter = filters.Document.MimeType("application/vnd.openxmlformats-officedocument.wordprocessingml.document") | filters.Document.FileExtension("docx")
    zip_filter = filters.Document.MimeType("application/zip") | filters.Document.MimeType("application/x-zip-compressed") | filters.Document.FileExtension("zip")
    application.add_handler(MessageHandler(epub_filter | pdf_filter | md_filter | docx_filter | zip_filter, document_handler))

    # Register message handler for URLs (plain text messages, not commands)
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            url_message_handler,
        )
    )

    # Global error handler
    application.add_error_handler(_error_handler)

    return application


async def _error_handler(update, context) -> None:
    """Log unhandled errors and notify the user."""
    logger.error(
        "Unhandled bot error",
        extra=format_error(context.error),
        error_code=ErrorCodes.INT_UNEXPECTED,
    )
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Something went wrong. Please try again later."
            )
        except Exception:
            pass


async def setup_webhook(application: Application) -> None:
    """Initialize the bot and set the Telegram webhook.

    Call this during FastAPI startup.
    """
    await application.initialize()
    await application.start()

    if not settings.TELEGRAM_WEBHOOK_URL:
        logger.warning("TELEGRAM_WEBHOOK_URL not set, skipping webhook registration. Set it after configuring reverse proxy.")
        return

    webhook_url = f"{settings.TELEGRAM_WEBHOOK_URL}/api/telegram/webhook"

    await application.bot.set_webhook(
        url=webhook_url,
        secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
    )

    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("help", "How to use PaperDrop"),
        BotCommand("settings", "Kindle email & preferences"),
        BotCommand("history", "Recent conversions"),
        BotCommand("status", "Subscription & usage"),
        BotCommand("subscribe", "Upgrade to Pro"),
    ])

    await application.bot.set_my_short_description(
        "Send any article, document, or ebook — get a Kindle-ready EPUB back instantly."
    )
    await application.bot.set_my_description(
        "PaperDrop converts articles and documents into Kindle-ready EPUBs.\n\n"
        "Just send a link, drop a file, and get your EPUB back in seconds. "
        "Set up your Kindle email in /settings and we'll deliver straight to your library.\n\n"
        "What it handles:\n"
        "- Web articles (any public URL)\n"
        "- EPUB files (fixes broken exports from Apple Books, Calibre, etc.)\n"
        "- PDF files (converts to reflowable EPUB)\n"
        "- Word documents (.docx)\n"
        "- Markdown files (.md)\n\n"
        "Free tier: 5 conversions. Pro: unlimited."
    )

    logger.info(
        "Webhook and commands set",
        extra={"webhook_url": webhook_url},
    )


async def shutdown_bot(application: Application) -> None:
    """Clean up bot resources. Call this during FastAPI shutdown."""
    try:
        await application.bot.delete_webhook()
        logger.info("Webhook deleted")
    except Exception as exc:
        logger.error(
            "Failed to delete webhook",
            extra=format_error(exc),
            error_code=ErrorCodes.API_UNAVAILABLE,
        )

    await application.stop()
    await application.shutdown()

    logger.info("Bot shutdown complete")
