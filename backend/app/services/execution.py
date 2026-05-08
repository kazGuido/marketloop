from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Pattern, Trade
from app.models.enums import PatternDirection, PatternStatus, TradeStatus
from app.services.hyperliquid_client import HyperliquidPrivateClient
from app.services.technical import stop_loss_from_x, take_profit_1


async def open_trade_for_pattern(
    session: AsyncSession,
    private_client: HyperliquidPrivateClient,
    pattern: Pattern,
    entry_price: float,
    risk_per_trade: float,
) -> Trade:
    stop_loss = stop_loss_from_x(pattern.coords, pattern.direction)
    risk_per_unit = abs(entry_price - stop_loss)
    if risk_per_unit <= 0:
        raise ValueError("Invalid stop loss geometry")

    equity = await private_client.account_equity()
    risk_amount = equity * (risk_per_trade / 100)
    quantity = max(risk_amount / risk_per_unit, 0)
    if quantity <= 0:
        raise ValueError("Calculated position size is zero")

    is_buy = pattern.direction == PatternDirection.BULLISH
    order = await private_client.market_open(pattern.symbol, is_buy=is_buy, size=quantity)
    order_id = _extract_order_id(order)

    trade = Trade(
        pattern_id=pattern.id,
        strategy_config_id=pattern.strategy_config_id,
        hyperliquid_order_id=order_id,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit_1=take_profit_1(pattern.coords, pattern.direction, entry_price),
        quantity=quantity,
        remaining_quantity=quantity,
        status=TradeStatus.OPEN,
    )
    pattern.status = PatternStatus.ACTIVE
    session.add(trade)
    await session.commit()
    await session.refresh(trade)
    return trade


async def close_trade_loss(
    session: AsyncSession,
    private_client: HyperliquidPrivateClient,
    trade: Trade,
    pattern: Pattern,
) -> None:
    if trade.remaining_quantity > 0:
        await private_client.market_close(pattern.symbol, trade.remaining_quantity)
    trade.remaining_quantity = 0
    trade.status = TradeStatus.CLOSED_LOSS
    pattern.status = PatternStatus.INVALIDATED
    await session.commit()


async def close_trade_take_profit(
    session: AsyncSession,
    private_client: HyperliquidPrivateClient,
    trade: Trade,
    pattern: Pattern,
) -> None:
    close_size = trade.remaining_quantity * 0.5
    if close_size <= 0:
        return
    await private_client.market_close(pattern.symbol, close_size)
    trade.remaining_quantity -= close_size
    trade.stop_loss = trade.entry_price
    trade.stop_moved_to_breakeven = True
    pattern.status = PatternStatus.WON
    await session.commit()


def _extract_order_id(order: dict) -> str | None:
    try:
        statuses = order["response"]["data"]["statuses"]
        first = statuses[0]
        return str(first.get("resting", {}).get("oid") or first.get("filled", {}).get("oid") or "")
    except (KeyError, IndexError, TypeError):
        return None
