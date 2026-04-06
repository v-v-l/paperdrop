"""DB resilience: retry with backoff + Redis pending-writes queue.

When the database is temporarily unavailable, DB writes are retried with
exponential backoff. If all retries fail, the write is serialized to a Redis
list and replayed later by a periodic drain task in the ARQ worker.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone

from logs_flow import ErrorCodes, create_logger, format_error
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError

from app.models.conversion import Conversion
from app.models.user import User

logger = create_logger(service="db-resilience")

PENDING_WRITES_KEY = "paperdrop:pending_db_writes"
DB_ERRORS = (InterfaceError, OperationalError, OSError)
MAX_RETRIES = 3
BASE_DELAY = 1.0


def generate_conversion_id() -> str:
    return str(uuid.uuid4())


async def db_retry(session_factory, operation, max_retries=MAX_RETRIES, base_delay=BASE_DELAY):
    """Execute a DB operation with retry and exponential backoff.

    ``operation`` is an async callable(session). This function opens a session,
    calls operation, commits, and returns the result. On transient DB errors it
    retries up to ``max_retries`` times with exponential backoff.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            async with session_factory() as session:
                result = await operation(session)
                await session.commit()
                return result
        except DB_ERRORS as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"DB operation failed (attempt {attempt + 1}/{max_retries + 1}), "
                    f"retrying in {delay}s",
                    extra=format_error(exc),
                )
                await asyncio.sleep(delay)
    raise last_exc


async def _execute_op(session, op_type: str, params: dict):
    """Execute a single DB write operation from its serialized description."""
    if op_type == "create_conversion":
        session.add(Conversion(**params))
    elif op_type == "update_conversion":
        p = dict(params)
        conv_id = p.pop("id")
        await session.execute(
            update(Conversion).where(Conversion.id == conv_id).values(**p)
        )
    elif op_type == "increment_user_conversions":
        await session.execute(
            update(User)
            .where(User.id == params["user_id"])
            .values(total_conversions=User.total_conversions + 1)
        )
    else:
        raise ValueError(f"Unknown pending write op: {op_type}")


async def resilient_db_write(session_factory, redis, op_type: str, params: dict) -> None:
    """Try a DB write with retry; queue to Redis if all attempts fail."""
    async def operation(session):
        await _execute_op(session, op_type, params)

    try:
        await db_retry(session_factory, operation)
    except DB_ERRORS as exc:
        logger.warning(
            f"All DB retries exhausted for {op_type}, queueing to Redis",
            extra=format_error(exc),
        )
        entry = json.dumps({
            "op": op_type,
            "params": params,
            "queued_at": datetime.now(timezone.utc).isoformat(),
        })
        await redis.lpush(PENDING_WRITES_KEY, entry)


async def drain_pending_writes(session_factory, redis) -> int:
    """Replay pending DB writes from Redis. Returns count of drained ops."""
    drained = 0
    while True:
        raw = await redis.rpop(PENDING_WRITES_KEY)
        if not raw:
            break
        entry = json.loads(raw)
        try:
            async with session_factory() as session:
                await _execute_op(session, entry["op"], entry["params"])
                await session.commit()
            drained += 1
        except IntegrityError:
            # Record already exists (retry succeeded AND was queued) — skip
            drained += 1
        except DB_ERRORS:
            # DB still down — push back to head and stop draining
            await redis.rpush(PENDING_WRITES_KEY, raw)
            logger.warning("DB still unavailable during drain, will retry later")
            break
        except Exception as exc:
            logger.error(
                "Failed to replay pending write, discarding",
                extra={"entry": entry, **format_error(exc)},
                error_code=ErrorCodes.INT_UNEXPECTED,
            )
    if drained:
        logger.info(f"Drained {drained} pending DB write(s)")
    return drained
