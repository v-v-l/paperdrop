import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from logs_flow import ErrorCodes, create_logger, format_error
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.metrics import router as metrics_router
from app.api.miniapp import router as miniapp_router
from app.api.webhook import router as webhook_router
from app.core.config import settings
from app.core.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage bot lifecycle: setup webhook on startup, clean up on shutdown."""
    # Startup
    application = create_bot_application()
    app.state.bot_application = application

    try:
        await setup_webhook(application)
        logger.info("Bot webhook setup complete")
    except Exception as exc:
        logger.error(
            "Failed to setup bot webhook",
            extra=format_error(exc),
            error_code=ErrorCodes.API_UNAVAILABLE,
        )

    yield

    # Shutdown
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
    title="Links to EPUB",
    version="0.1.0",
    description="Telegram bot backend for converting links to EPUB",
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
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.APP_PORT,
        reload=True,
    )
