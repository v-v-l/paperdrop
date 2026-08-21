import asyncio
import os
import time
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from logs_flow import ErrorCodes, create_logger, format_error
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.metrics import router as metrics_router
from app.api.miniapp import router as miniapp_router
from app.api.webhook import router as webhook_router
from app.core.config import settings
from app.core.metrics import BOT_WEBHOOK_HEALTHY, HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL
from app.services.telegram.bot import create_bot_application, setup_webhook, shutdown_bot

logger = create_logger(service="links-to-epub")

METRICS_EXCLUDE_PATHS = {"/metrics", "/health"}


class MetricsMiddleware(BaseHTTPMiddleware):
    """Track HTTP request count and latency for Prometheus."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in METRICS_EXCLUDE_PATHS:
            return await call_next(request)

        method = request.method
        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start

        endpoint = request.url.path
        status = str(response.status_code)

        HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status=status).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(duration)

        return response


WEBHOOK_RETRY_ATTEMPTS = 5
WEBHOOK_RETRY_BASE_DELAY = 2  # seconds, doubles each attempt
WEBHOOK_RECOVERY_MAX_DELAY = 60  # cap for the background recovery loop


async def _setup_webhook_with_retry(application) -> bool:
    """Try to set up the webhook with exponential backoff.

    Bounded so startup cannot hang indefinitely on a dead dependency; callers
    hand a failure off to _recover_webhook_forever.
    """
    for attempt in range(1, WEBHOOK_RETRY_ATTEMPTS + 1):
        try:
            await setup_webhook(application)
            BOT_WEBHOOK_HEALTHY.set(1)
            logger.info("Bot webhook setup complete", extra={"attempt": attempt})
            return True
        except Exception as exc:
            delay = WEBHOOK_RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                "Webhook setup failed, retrying",
                extra={
                    "attempt": attempt,
                    "max_attempts": WEBHOOK_RETRY_ATTEMPTS,
                    "retry_in_seconds": delay,
                    **format_error(exc),
                },
            )
            if attempt < WEBHOOK_RETRY_ATTEMPTS:
                await asyncio.sleep(delay)

    BOT_WEBHOOK_HEALTHY.set(0)
    logger.error(
        "Webhook setup failed after all retries",
        extra={"attempts": WEBHOOK_RETRY_ATTEMPTS},
        error_code=ErrorCodes.API_UNAVAILABLE,
    )
    return False


async def _recover_webhook_forever(application) -> None:
    """Keep retrying webhook setup in the background until it succeeds.

    On an unattended restart Docker brings every container up in parallel and
    ignores depends_on, so the local Bot API server can outlast the bounded
    startup retries. Without this the webhook stays unregistered and the health
    gauge reads 0 for the life of the process even once the dependency recovers.
    Costs one background task and one setup attempt per interval while broken;
    the loop exits on the first success.
    """
    delay = WEBHOOK_RETRY_BASE_DELAY
    attempt = 0
    while True:
        await asyncio.sleep(delay)
        attempt += 1
        try:
            await setup_webhook(application)
            BOT_WEBHOOK_HEALTHY.set(1)
            logger.info("Bot webhook recovered", extra={"attempt": attempt})
            return
        except Exception as exc:
            delay = min(delay * 2, WEBHOOK_RECOVERY_MAX_DELAY)
            logger.warning(
                "Webhook recovery failed, retrying",
                extra={"attempt": attempt, "retry_in_seconds": delay, **format_error(exc)},
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage bot lifecycle: setup webhook on startup, clean up on shutdown."""
    # Startup
    application = create_bot_application()
    app.state.bot_application = application

    recovery_task: asyncio.Task | None = None
    if not await _setup_webhook_with_retry(application):
        recovery_task = asyncio.create_task(_recover_webhook_forever(application))

    yield

    # Shutdown
    if recovery_task is not None and not recovery_task.done():
        recovery_task.cancel()
        with suppress(asyncio.CancelledError):
            await recovery_task

    try:
        await shutdown_bot(application)
        logger.info("Bot shutdown complete")
    except Exception as exc:
        logger.error(
            "Failed to shut down bot",
            extra=format_error(exc),
            error_code=ErrorCodes.API_UNAVAILABLE,
        )


app = FastAPI(
    title="PaperDrop",
    version="0.1.0",
    description="PaperDrop — Telegram bot for converting articles to EPUB",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(MetricsMiddleware)

app.include_router(webhook_router)
app.include_router(miniapp_router)
app.include_router(metrics_router)

# Serve Mini App static files if the directory exists
miniapp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "miniapp")
if os.path.isdir(miniapp_dir):
    app.mount("/miniapp", StaticFiles(directory=miniapp_dir, html=True), name="miniapp")


@app.get("/health")
async def health() -> dict:
    bot_healthy = BOT_WEBHOOK_HEALTHY._value.get() == 1
    return {
        "status": "ok" if bot_healthy else "degraded",
        "bot_webhook": "healthy" if bot_healthy else "unhealthy",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.APP_PORT,
        reload=True,
    )
