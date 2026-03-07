from arq import ArqRedis

from app.services.tasks.conversion_task import process_conversion
from app.services.tasks.file_task import process_file


async def enqueue_conversion(
    redis: ArqRedis,
    user_id: int,
    url: str,
    chat_id: int,
    message_id: int,
    grayscale: bool = True,
) -> None:
    """Enqueue a URL-to-EPUB conversion job via ARQ."""
    await redis.enqueue_job(
        "process_conversion",
        user_id=user_id,
        url=url,
        chat_id=chat_id,
        message_id=message_id,
        grayscale=grayscale,
    )


async def enqueue_file(
    redis: ArqRedis,
    user_id: int,
    chat_id: int,
    message_id: int,
    file_bytes: bytes,
    filename: str,
    file_type: str,
) -> None:
    """Enqueue a file processing job (EPUB fix or PDF conversion) via ARQ."""
    await redis.enqueue_job(
        "process_file",
        user_id=user_id,
        chat_id=chat_id,
        message_id=message_id,
        file_bytes=file_bytes,
        filename=filename,
        file_type=file_type,
    )


__all__ = ["enqueue_conversion", "enqueue_file", "process_conversion", "process_file"]
