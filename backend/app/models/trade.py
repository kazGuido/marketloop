import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
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
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_1: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    remaining_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    stop_moved_to_breakeven: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[TradeStatus] = mapped_column(Enum(TradeStatus), nullable=False, default=TradeStatus.OPEN, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    pattern = relationship("Pattern", back_populates="trade")
