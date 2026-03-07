"""Subscription management service for Telegram Payments."""

from datetime import datetime, timedelta, timezone

from logs_flow import create_logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User

logger = create_logger(service="subscription-service")

SUBSCRIPTION_PERIOD_DAYS = 30


async def create_subscription(
    db: AsyncSession,
    user_id: int,
    charge_id: str,
    provider_charge_id: str,
) -> Subscription:
    """Create or renew a subscription with a 30-day period.

    If the user already has a subscription row, it is updated in place
    (the table has a unique constraint on user_id).
    """
    now = datetime.now(timezone.utc)
    period_end = now + timedelta(days=SUBSCRIPTION_PERIOD_DAYS)

    existing = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    subscription = existing.scalar_one_or_none()

    if subscription is not None:
        subscription.telegram_payment_charge_id = charge_id
        subscription.provider_payment_charge_id = provider_charge_id
        subscription.status = SubscriptionStatus.ACTIVE.value
        subscription.current_period_start = now
        subscription.current_period_end = period_end
    else:
        subscription = Subscription(
            user_id=user_id,
            telegram_payment_charge_id=charge_id,
            provider_payment_charge_id=provider_charge_id,
            status=SubscriptionStatus.ACTIVE.value,
            current_period_start=now,
            current_period_end=period_end,
        )
        db.add(subscription)

    await db.commit()
    await db.refresh(subscription)

    logger.info(
        "Subscription created",
        extra={
            "user_id": user_id,
            "subscription_id": subscription.id,
            "period_end": period_end.isoformat(),
        },
    )

    return subscription


async def check_subscription(db: AsyncSession, user_id: int) -> bool:
    """Return True if the user has an active, non-expired subscription.

    If the subscription period has ended, it is automatically marked as expired.
    """
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription is None:
        return False

    if subscription.status != SubscriptionStatus.ACTIVE.value:
        return False

    now = datetime.now(timezone.utc)
    if subscription.current_period_end and subscription.current_period_end < now:
        subscription.status = SubscriptionStatus.EXPIRED.value
        await db.commit()
        logger.info(
            "Subscription auto-expired",
            extra={"user_id": user_id, "subscription_id": subscription.id},
        )
        return False

    return True


async def can_convert(db: AsyncSession, user_id: int) -> tuple[bool, str]:
    """Check whether the user is allowed to perform a conversion.

    Returns:
        (allowed, reason) -- reason is empty when allowed, or a human-readable
        explanation when denied.
    """
    if await check_subscription(db, user_id):
        return True, ""

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        return False, "User not found."

    if user.total_conversions < settings.FREE_TIER_LIMIT:
        return True, ""

    return False, f"Free tier limit of {settings.FREE_TIER_LIMIT} conversions reached."
