from arq import ArqRedis

from app.services.tasks.conversion_task import process_conversion


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


__all__ = ["enqueue_conversion", "process_conversion"]
