from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import TradeStatus


class TradeRead(BaseModel):
    id: UUID
    pattern_id: UUID
    entry_price: float
    stop_loss: float
    take_profit_1: float
    quantity: float
    remaining_quantity: float
    status: TradeStatus
    created_at: datetime

    model_config = {"from_attributes": True}
