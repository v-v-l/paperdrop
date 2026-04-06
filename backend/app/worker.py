"""ARQ worker entry point.

Run with: arq backend.app.worker.WorkerSettings
"""

from arq.connections import RedisSettings
from arq.cron import cron

from logs_flow import create_logger, format_error, ErrorCodes

from app.core.config import settings
from app.services.tasks import process_conversion, process_file

logger = create_logger(service="arq-worker")


def parse_redis_settings(redis_url: str) -> RedisSettings:
    """Parse a redis:// URL into ARQ RedisSettings."""
    from urllib.parse import urlparse

    parsed = urlparse(redis_url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or 0),
        password=parsed.password,
    )


async def startup(ctx: dict) -> None:
    """Initialize resources for the worker: DB engine, Telegram bot, temp dir."""
    import os

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from telegram import Bot

    logger.info("Worker starting up")

    # Database
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Telegram bot
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

    # Temp directory
    temp_dir = settings.TEMP_DIR
    os.makedirs(temp_dir, exist_ok=True)

    ctx["engine"] = engine
    ctx["session_factory"] = session_factory
    ctx["bot"] = bot
    ctx["temp_dir"] = temp_dir

    logger.info("Worker startup complete")


async def shutdown(ctx: dict) -> None:
    """Clean up resources on worker shutdown."""
    logger.info("Worker shutting down")

    try:
        engine = ctx.get("engine")
        if engine:
            await engine.dispose()
    except Exception as exc:
        logger.error(
            "Error disposing DB engine",
            extra=format_error(exc),
            error_code=ErrorCodes.DB_CONN_REFUSED,
        )

    try:
        bot = ctx.get("bot")
        if bot:
            await bot.shutdown()
    except Exception as exc:
        logger.error(
            "Error shutting down bot",
            extra=format_error(exc),
            error_code=ErrorCodes.API_UNAVAILABLE,
        )

    logger.info("Worker shutdown complete")


async def drain_db_queue(ctx: dict) -> None:
    """Periodic task: replay any DB writes queued during database outages."""
    from app.core.db_resilience import drain_pending_writes

    await drain_pending_writes(ctx["session_factory"], ctx["redis"])


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [process_conversion, process_file]
    cron_jobs = [cron(drain_db_queue, second={0})]
    redis_settings = parse_redis_settings(settings.REDIS_URL)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 5
    job_timeout = 120
    health_check_interval = 30
