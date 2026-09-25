"""Уведомления через Telegram Bot API."""
import logging

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)
API = "https://api.telegram.org/bot{token}/{method}"


def enabled() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN)


def call(method: str, **params) -> dict:
    url = API.format(token=settings.TELEGRAM_BOT_TOKEN, method=method)
    resp = httpx.post(url, json=params, timeout=35)
    resp.raise_for_status()
    return resp.json()


def send_message(chat_id: str, text: str) -> None:
    if not enabled() or not chat_id:
        return
    call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML", disable_web_page_preview=True)


def bot_username() -> str | None:
    if not enabled():
        return None
    try:
        return call("getMe")["result"]["username"]
    except Exception:
        log.warning("Telegram getMe failed", exc_info=True)
        return None


def get_updates(offset: int) -> list[dict]:
    return call("getUpdates", offset=offset, timeout=0, allowed_updates=["message"]).get("result", [])
