import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import TradeStatus


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pattern_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patterns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    strategy_config_id: Mapped[int | None] = mapped_column(ForeignKey("strategy_configs.id"), nullable=True, index=True)
    hyperliquid_order_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    requested_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    average_fill_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_1: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    remaining_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    exchange_position_size: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    stop_moved_to_breakeven: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[TradeStatus] = mapped_column(Enum(TradeStatus), nullable=False, default=TradeStatus.OPEN, index=True)
    reconciliation_notes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    pattern = relationship("Pattern", back_populates="trade")
