import httpx

from app.core.config import get_settings
from app.models import Pattern
from app.services.confluence import ConfluenceResult


async def send_pattern_alert(pattern: Pattern, confluence: ConfluenceResult) -> None:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return

    x = pattern.coords["X"]["price"]
    c = pattern.coords["C"]["price"]
    message = (
        f"{pattern.direction} {pattern.pattern_type} on {pattern.symbol} {pattern.timeframe}\n"
        f"Score: {confluence.score}/100\n"
        f"PRZ: {pattern.prz_lower:.4f} - {pattern.prz_upper:.4f}\n"
        f"X: {x} | C: {c}\n"
        f"Reasons: {', '.join(confluence.reasons)}"
    )
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            url,
            json={"chat_id": settings.telegram_chat_id, "text": message},
        )
        response.raise_for_status()
