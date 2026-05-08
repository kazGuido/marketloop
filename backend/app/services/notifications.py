import asyncio
import smtplib
from email.message import EmailMessage
from typing import Any

import httpx

from app.core.config import get_settings
from app.models import Pattern, StrategyConfig, StrategyPerformanceSnapshot, SystemConfig
from app.services.confluence import ConfluenceResult


async def send_pattern_alert(config: SystemConfig, pattern: Pattern, confluence: ConfluenceResult) -> None:
    subject = f"{pattern.symbol} {pattern.timeframe} {pattern.pattern_type} score {confluence.score}"
    message = _pattern_message(pattern, confluence)
    await _fanout(config, subject, message)


async def send_strategy_degradation_alert(
    config: SystemConfig,
    strategy: StrategyConfig,
    snapshot: StrategyPerformanceSnapshot,
) -> None:
    subject = f"Strategy degradation: {strategy.name}"
    message = (
        f"Strategy degradation detected: {strategy.name} (id={strategy.id})\n"
        f"Sample: {snapshot.sample_size}\n"
        f"Win rate: {snapshot.win_rate:.1%}\n"
        f"Profit factor: {snapshot.profit_factor:.2f}\n"
        f"Expectancy: {snapshot.expectancy_r:.2f}R\n"
        f"Max DD: {snapshot.max_drawdown_r:.2f}R\n"
        "Action: replay saved strategies or clone tighter/looser knobs before changing AUTO_TRADE."
    )
    await _fanout(config, subject, message)


async def _fanout(config: SystemConfig, subject: str, message: str) -> None:
    notification_config = _notification_config(config)
    tasks = []
    if notification_config.get("telegram_enabled", True):
        tasks.append(_send_telegram(notification_config, message))
    if notification_config.get("whatsapp_enabled"):
        tasks.append(_send_whatsapp(notification_config, message))
    if notification_config.get("email_enabled"):
        tasks.append(_send_email(notification_config, subject, message))
    if not tasks:
        return
    await asyncio.gather(*tasks, return_exceptions=True)


async def _send_telegram(notification_config: dict[str, Any], message: str) -> None:
    settings = get_settings()
    chat_id = notification_config.get("telegram_chat_id") or settings.telegram_chat_id
    if not settings.telegram_bot_token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, json={"chat_id": chat_id, "text": message})
        response.raise_for_status()


async def _send_whatsapp(notification_config: dict[str, Any], message: str) -> None:
    settings = get_settings()
    recipient = notification_config.get("whatsapp_recipient")
    if not recipient:
        return
    bridge_url = (notification_config.get("whatsapp_bridge_url") or settings.whatsapp_bridge_url).rstrip("/")
    headers = {}
    if settings.whatsapp_bridge_api_key:
        headers["x-api-key"] = settings.whatsapp_bridge_api_key
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(f"{bridge_url}/send", json={"to": recipient, "message": message}, headers=headers)
        response.raise_for_status()


async def _send_email(notification_config: dict[str, Any], subject: str, message: str) -> None:
    settings = get_settings()
    to_email = notification_config.get("email_to")
    host = notification_config.get("smtp_host") or settings.smtp_host
    from_email = notification_config.get("email_from") or settings.smtp_from_email or settings.smtp_username
    if not to_email or not host or not from_email:
        return

    smtp_config = {
        "host": host,
        "port": int(notification_config.get("smtp_port") or settings.smtp_port),
        "username": notification_config.get("smtp_username") or settings.smtp_username,
        "password": notification_config.get("smtp_password") or settings.smtp_password,
        "use_tls": bool(notification_config.get("smtp_use_tls", settings.smtp_use_tls)),
        "from_email": from_email,
        "to_email": to_email,
        "subject": subject,
        "message": message,
    }
    await asyncio.to_thread(_send_email_sync, smtp_config)


def _send_email_sync(smtp_config: dict[str, Any]) -> None:
    email = EmailMessage()
    email["From"] = smtp_config["from_email"]
    email["To"] = smtp_config["to_email"]
    email["Subject"] = smtp_config["subject"]
    email.set_content(smtp_config["message"])

    with smtplib.SMTP(smtp_config["host"], smtp_config["port"], timeout=15) as smtp:
        if smtp_config["use_tls"]:
            smtp.starttls()
        if smtp_config["username"] and smtp_config["password"]:
            smtp.login(smtp_config["username"], smtp_config["password"])
        smtp.send_message(email)


def _pattern_message(pattern: Pattern, confluence: ConfluenceResult) -> str:
    x = pattern.coords["X"]["price"]
    c = pattern.coords["C"]["price"]
    return (
        f"{pattern.direction} {pattern.pattern_type} on {pattern.symbol} {pattern.timeframe}\n"
        f"Score: {confluence.score}/100\n"
        f"PRZ: {pattern.prz_lower:.4f} - {pattern.prz_upper:.4f}\n"
        f"X: {x} | C: {c}\n"
        f"Reasons: {', '.join(confluence.reasons)}"
    )


def _notification_config(config: SystemConfig) -> dict[str, Any]:
    return config.notification_config or {}
