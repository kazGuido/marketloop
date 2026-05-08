from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import PatternDirection, PatternStatus


class PatternRead(BaseModel):
    id: UUID
    symbol: str
    pattern_type: str
    direction: PatternDirection
    timeframe: str
    coords: dict[str, Any]
    prz_upper: float
    prz_lower: float
    confluence_score: int
    confluence_details: dict[str, Any]
    status: PatternStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class CandleRead(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
