from enum import StrEnum


class OperationMode(StrEnum):
    SIGNAL_ONLY = "SIGNAL_ONLY"
    AUTO_TRADE = "AUTO_TRADE"


class PatternStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    INVALIDATED = "INVALIDATED"
    WON = "WON"
    LOST = "LOST"


class TradeStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED_WIN = "CLOSED_WIN"
    CLOSED_LOSS = "CLOSED_LOSS"


class PatternDirection(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
