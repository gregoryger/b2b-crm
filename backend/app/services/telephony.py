"""Интеграция с SIP-АТС.

Провайдер «mock» — для демонстрации и тестов: звонок фиксируется в CRM без реального дозвона.
Провайдер «generic_http» — вызывает HTTP API АТС (Asterisk ARI-прокси, Манго, Mango Office, UIS, Zadarma и т.п.
подключаются через тонкий адаптер, принимающий JSON {from, to}).
Входящие события АТС присылает на вебхук /api/v1/integrations/telephony/events.
"""
import uuid

import httpx

from app.core.config import settings


class TelephonyError(Exception):
    pass


def click_to_call(extension: str | None, phone: str) -> dict:
    if settings.TELEPHONY_PROVIDER == "mock":
        return {"call_id": f"mock-{uuid.uuid4().hex[:12]}", "provider": "mock", "status": "initiated"}
    if not settings.TELEPHONY_API_URL:
        raise TelephonyError("Не задан адрес API телефонии")
    if not extension:
        raise TelephonyError("У пользователя не указан внутренний номер SIP")
    try:
        resp = httpx.post(settings.TELEPHONY_API_URL, json={"from": extension, "to": phone},
                          headers={"Authorization": f"Bearer {settings.TELEPHONY_API_TOKEN}"}, timeout=10)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise TelephonyError(f"АТС не ответила: {exc}") from exc
    data = resp.json() if resp.content else {}
    return {"call_id": str(data.get("call_id") or uuid.uuid4().hex), "provider": "generic_http", "status": "initiated"}
