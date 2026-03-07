"""Pydantic schemas for Mini App API endpoints."""

from datetime import datetime

from pydantic import BaseModel, field_validator


class AuthRequest(BaseModel):
    init_data: str


class AuthResponse(BaseModel):
    user_id: int
    username: str | None = None
    first_name: str | None = None
    is_subscribed: bool = False
    total_conversions: int = 0
    free_tier_limit: int = 5


class SettingsResponse(BaseModel):
    kindle_email: str | None = None
    grayscale_images: bool = True


class SettingsUpdate(BaseModel):
    kindle_email: str | None = None
    grayscale_images: bool | None = None

    @field_validator("kindle_email")
    @classmethod
    def validate_kindle_email(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.strip().lower()
        if not v.endswith("@kindle.com") and not v.endswith("@free.kindle.com"):
            raise ValueError("Email must end with @kindle.com or @free.kindle.com")
        return v


class ConversionHistoryItem(BaseModel):
    id: str
    url: str
    title: str | None = None
    status: str
    file_size_bytes: int | None = None
    created_at: datetime


class ConversionHistoryResponse(BaseModel):
    items: list[ConversionHistoryItem]
    next_cursor: str | None = None


class SubscriptionStatusResponse(BaseModel):
    is_subscribed: bool = False
    status: str | None = None
    current_period_end: datetime | None = None
    total_conversions: int = 0
    free_tier_limit: int = 5
