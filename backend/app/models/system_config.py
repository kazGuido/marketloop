from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Float, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import OperationMode


class SystemConfig(Base):
    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    operation_mode: Mapped[OperationMode] = mapped_column(
        Enum(OperationMode), nullable=False, default=OperationMode.SIGNAL_ONLY
    )
    asset_pool: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=lambda: ["BTC", "ETH", "SOL"])
    risk_per_trade: Mapped[float] = mapped_column(Float, nullable=False, default=1.5)
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
