"""Mini App API endpoints for settings, history, and subscription management."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from logs_flow import ErrorCodes, create_logger, format_error
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.models.conversion import Conversion
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
from app.schemas.miniapp import (
    AuthRequest,
    AuthResponse,
    ConversionHistoryItem,
    ConversionHistoryResponse,
    SettingsResponse,
    SettingsUpdate,
    SubscriptionStatusResponse,
)
from app.services.telegram.auth import validate_init_data

logger = create_logger(service="miniapp-api")

router = APIRouter(prefix="/api/miniapp", tags=["miniapp"])


async def get_current_user_id(
    authorization: str = Header(..., description="Telegram WebApp initData"),
) -> int:
    """FastAPI dependency: extract and validate initData from Authorization header.

    Returns the telegram user_id.
    """
    user_data = validate_init_data(authorization, settings.TELEGRAM_BOT_TOKEN)
    return user_data["user_id"]


@router.post("/auth", response_model=AuthResponse)
async def auth(
    body: AuthRequest,
    db: AsyncSession = Depends(get_session),
) -> AuthResponse:
    """Validate initData, upsert user, return profile + subscription status."""
    user_data = validate_init_data(body.init_data, settings.TELEGRAM_BOT_TOKEN)
    user_id = user_data["user_id"]

    # Upsert user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            id=user_id,
            username=user_data.get("username"),
            first_name=user_data.get("first_name"),
            language_code=user_data.get("language_code"),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("New user created via miniapp auth", extra={"user_id": user_id})
    else:
        # Update user info from Telegram
        user.username = user_data.get("username")
        user.first_name = user_data.get("first_name")
        user.language_code = user_data.get("language_code")
        await db.commit()

    # Check subscription
    is_subscribed = False
    if user.subscription is not None:
        sub = user.subscription
        if sub.status == SubscriptionStatus.ACTIVE.value:
            now = datetime.now(timezone.utc)
            if sub.current_period_end and sub.current_period_end >= now:
                is_subscribed = True
            else:
                sub.status = SubscriptionStatus.EXPIRED.value
                await db.commit()

    return AuthResponse(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        is_subscribed=is_subscribed,
        total_conversions=user.total_conversions,
        free_tier_limit=settings.FREE_TIER_LIMIT,
    )


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session),
) -> SettingsResponse:
    """Get user settings."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return SettingsResponse(
        kindle_email=user.kindle_email,
        grayscale_images=user.grayscale_images,
    )


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session),
) -> SettingsResponse:
    """Update user settings (kindle_email, grayscale_images)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if body.kindle_email is not None:
        user.kindle_email = body.kindle_email if body.kindle_email != "" else None
    if body.grayscale_images is not None:
        user.grayscale_images = body.grayscale_images

    await db.commit()
    await db.refresh(user)

    logger.info("User settings updated", extra={"user_id": user_id})

    return SettingsResponse(
        kindle_email=user.kindle_email,
        grayscale_images=user.grayscale_images,
    )


@router.get("/history", response_model=ConversionHistoryResponse)
async def get_history(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session),
    cursor: str | None = Query(None, description="ISO datetime cursor for pagination"),
    limit: int = Query(20, ge=1, le=50, description="Number of items per page"),
) -> ConversionHistoryResponse:
    """Get paginated conversion history using cursor-based pagination on created_at."""
    query = (
        select(Conversion)
        .where(Conversion.user_id == user_id)
        .order_by(Conversion.created_at.desc())
        .limit(limit + 1)
    )

    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cursor format, expected ISO datetime",
            )
        query = query.where(Conversion.created_at < cursor_dt)

    result = await db.execute(query)
    conversions = list(result.scalars().all())

    # Determine next cursor
    next_cursor = None
    if len(conversions) > limit:
        conversions = conversions[:limit]
        next_cursor = conversions[-1].created_at.isoformat()

    items = [
        ConversionHistoryItem(
            id=str(c.id),
            url=c.url,
            title=c.title,
            status=c.status,
            file_size_bytes=c.file_size_bytes,
            created_at=c.created_at,
        )
        for c in conversions
    ]

    return ConversionHistoryResponse(items=items, next_cursor=next_cursor)


@router.get("/subscription", response_model=SubscriptionStatusResponse)
async def get_subscription(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session),
) -> SubscriptionStatusResponse:
    """Get subscription status, expiry, and conversion count."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    is_subscribed = False
    sub_status = None
    period_end = None

    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    subscription = sub_result.scalar_one_or_none()

    if subscription is not None:
        sub_status = subscription.status
        period_end = subscription.current_period_end

        if subscription.status == SubscriptionStatus.ACTIVE.value:
            now = datetime.now(timezone.utc)
            if period_end and period_end >= now:
                is_subscribed = True
            else:
                subscription.status = SubscriptionStatus.EXPIRED.value
                sub_status = SubscriptionStatus.EXPIRED.value
                await db.commit()

    return SubscriptionStatusResponse(
        is_subscribed=is_subscribed,
        status=sub_status,
        current_period_end=period_end,
        total_conversions=user.total_conversions,
        free_tier_limit=settings.FREE_TIER_LIMIT,
    )
