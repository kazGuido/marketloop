from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import TradeStatus


class TradeRead(BaseModel):
    id: UUID
    pattern_id: UUID
    strategy_config_id: int | None
    requested_quantity: float
    entry_price: float
    average_fill_price: float | None
    stop_loss: float
    take_profit_1: float
    quantity: float
    remaining_quantity: float
    exchange_position_size: float
    status: TradeStatus
    created_at: datetime

    model_config = {"from_attributes": True}
