from datetime import UTC, datetime
from typing import Any

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
    fill = _extract_fill_details(order, fallback_price=entry_price, requested_quantity=quantity)
    if fill["filled_size"] <= 0:
        raise RuntimeError(f"Hyperliquid market order did not report a fill: {order}")
    fill_price = fill["average_price"] or entry_price

    trade = Trade(
        pattern_id=pattern.id,
        strategy_config_id=pattern.strategy_config_id,
        hyperliquid_order_id=fill["order_id"],
        requested_quantity=quantity,
        entry_price=fill_price,
        average_fill_price=fill_price,
        stop_loss=stop_loss,
        take_profit_1=take_profit_1(pattern.coords, pattern.direction, fill_price),
        quantity=fill["filled_size"],
        remaining_quantity=fill["filled_size"],
        exchange_position_size=fill["filled_size"],
        reconciliation_notes={"open_order": order, "requested_quantity": quantity},
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
    close_size = await _reconciled_close_size(private_client, pattern, trade)
    if close_size > 0:
        await private_client.market_close(pattern.symbol, close_size)
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
    reconciled_size = await _reconciled_close_size(private_client, pattern, trade)
    close_size = reconciled_size * 0.5
    if close_size <= 0:
        return
    await private_client.market_close(pattern.symbol, close_size)
    trade.remaining_quantity = max(reconciled_size - close_size, 0)
    trade.exchange_position_size = trade.remaining_quantity
    trade.stop_loss = trade.entry_price
    trade.stop_moved_to_breakeven = True
    pattern.status = PatternStatus.WON
    await session.commit()


async def reconcile_trade_position(
    session: AsyncSession,
    private_client: HyperliquidPrivateClient,
    trade: Trade,
    pattern: Pattern,
) -> None:
    positions = await private_client.open_positions()
    position = positions.get(pattern.symbol.upper())
    exchange_abs_size = float(position.get("abs_size", 0) if position else 0)
    trade.exchange_position_size = exchange_abs_size
    trade.last_reconciled_at = datetime.now(UTC)
    trade.reconciliation_notes = {
        **(trade.reconciliation_notes or {}),
        "last_position": position or {},
        "previous_remaining_quantity": trade.remaining_quantity,
    }
    if exchange_abs_size <= 0:
        trade.remaining_quantity = 0
        trade.status = TradeStatus.CLOSED_LOSS
        pattern.status = PatternStatus.INVALIDATED
    elif exchange_abs_size < trade.remaining_quantity:
        trade.remaining_quantity = exchange_abs_size
    elif trade.remaining_quantity <= 0:
        trade.remaining_quantity = exchange_abs_size
    await session.commit()


async def _reconciled_close_size(
    private_client: HyperliquidPrivateClient,
    pattern: Pattern,
    trade: Trade,
) -> float:
    positions = await private_client.open_positions()
    position = positions.get(pattern.symbol.upper())
    if not position:
        return 0
    return min(float(position.get("abs_size", 0) or 0), trade.remaining_quantity or float(position.get("abs_size", 0) or 0))


def _extract_fill_details(order: dict[str, Any], fallback_price: float, requested_quantity: float) -> dict[str, Any]:
    order_id = None
    filled_size = 0.0
    notional = 0.0
    try:
        statuses = order["response"]["data"]["statuses"]
        for status in statuses:
            filled = status.get("filled") or {}
            resting = status.get("resting") or {}
            order_id = order_id or filled.get("oid") or resting.get("oid")
            size = float(filled.get("totalSz") or filled.get("sz") or 0)
            price = float(filled.get("avgPx") or filled.get("px") or fallback_price)
            if size > 0:
                filled_size += size
                notional += size * price
    except (KeyError, IndexError, TypeError):
        pass
    average_price = notional / filled_size if filled_size > 0 else fallback_price
    return {
        "order_id": str(order_id) if order_id else None,
        "filled_size": min(filled_size, requested_quantity) if filled_size > 0 else 0,
        "average_price": average_price,
    }
