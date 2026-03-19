"""Prometheus metrics endpoint."""

from fastapi import APIRouter, Response
from logs_flow import ErrorCodes, create_logger, format_error
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.database import async_session_factory
from app.core.metrics import refresh_db_metrics

logger = create_logger(service="metrics-api")

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics() -> Response:
    """Expose Prometheus metrics.

    DB-backed metrics (active_subscriptions, kindle_deliveries) are refreshed
    from the database on each scrape so they reflect worker-written data.
    """
    try:
        async with async_session_factory() as session:
            await refresh_db_metrics(session)
    except Exception as exc:
        logger.warning(
            "Failed to refresh DB metrics, serving stale values",
            extra=format_error(exc),
            error_code=ErrorCodes.DB_QUERY_FAILED,
        )

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
