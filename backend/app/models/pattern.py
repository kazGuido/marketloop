import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PatternDirection, PatternStatus


class Pattern(Base):
    __tablename__ = "patterns"
    __table_args__ = (
        UniqueConstraint("source_key", name="uq_patterns_source_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    pattern_type: Mapped[str] = mapped_column(String(80), nullable=False)
    direction: Mapped[PatternDirection] = mapped_column(Enum(PatternDirection), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False, default="15m")
    coords: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    prz_upper: Mapped[float] = mapped_column(Float, nullable=False)
    prz_lower: Mapped[float] = mapped_column(Float, nullable=False)
    confluence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[PatternStatus] = mapped_column(
        Enum(PatternStatus), nullable=False, default=PatternStatus.PENDING, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    trade = relationship("Trade", back_populates="pattern", uselist=False)
