from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False
    )
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    first_name: Mapped[str | None] = mapped_column(String, nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    kindle_email: Mapped[str | None] = mapped_column(String, nullable=True)
    grayscale_images: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    total_conversions: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    conversions = relationship("Conversion", back_populates="user", lazy="selectin")
    subscription = relationship(
        "Subscription", back_populates="user", uselist=False, lazy="selectin"
    )
