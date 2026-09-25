"""Лента активностей и журнал аудита."""
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models import Activity, AuditLog, Company, User

# Человекочитаемые названия полей для ленты изменений
FIELD_LABELS = {
    "name": "Наименование", "full_name": "Полное наименование", "inn": "ИНН", "kpp": "КПП", "ogrn": "ОГРН",
    "legal_address": "Юр. адрес", "actual_address": "Факт. адрес", "industry_id": "Отрасль", "region_id": "Регион",
    "client_type_id": "Тип клиента", "source_id": "Источник", "manager_id": "Ответственный", "status": "Статус",
    "phone": "Телефон", "email": "Email", "website": "Сайт", "description": "Описание",
    "last_name": "Фамилия", "first_name": "Имя", "middle_name": "Отчество", "position": "Должность",
    "phone_mobile": "Моб. телефон", "phone_work": "Раб. телефон", "telegram": "Telegram", "whatsapp": "WhatsApp",
    "role_in_deal": "Роль в сделке", "company_id": "Компания", "title": "Название", "amount": "Сумма",
    "currency": "Валюта", "probability": "Вероятность", "close_date": "Дата закрытия", "owner_id": "Ответственный",
    "stage_id": "Этап", "assigned_to": "Ответственный", "contact_id": "Контакт", "custom_fields": "Доп. поля",
    "bank_name": "Банк", "bik": "БИК", "account": "Р/с", "corr_account": "К/с",
}

SENSITIVE_FIELDS = {"phone", "phone_mobile", "phone_work"}


def _plain(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def apply_changes(obj: Any, data: dict) -> dict[str, list]:
    """Применяет изменения к объекту и возвращает diff {поле: [было, стало]}."""
    changes: dict[str, list] = {}
    for key, new in data.items():
        old = getattr(obj, key, None)
        if _plain(old) == _plain(new) or (old in (None, "") and new in (None, "")):
            continue
        setattr(obj, key, new)
        if key in SENSITIVE_FIELDS:
            changes[key] = ["***", "***"]
        else:
            changes[key] = [_plain(old), _plain(new)]
    return changes


def log_activity(
    db: Session,
    *,
    type: str,
    title: str,
    object_type: str,
    object_id: int,
    user: User | None = None,
    body: str | None = None,
    company_id: int | None = None,
    contact_id: int | None = None,
    deal_id: int | None = None,
    lead_id: int | None = None,
    meta: dict | None = None,
    occurred_at: datetime | None = None,
    touch_company: bool = False,
) -> Activity:
    act = Activity(
        type=type, title=title, body=body, user_id=user.id if user else None,
        object_type=object_type, object_id=object_id, company_id=company_id, contact_id=contact_id,
        deal_id=deal_id, lead_id=lead_id, meta=meta or {}, occurred_at=occurred_at or utcnow(),
    )
    db.add(act)
    if touch_company and company_id:
        company = db.get(Company, company_id)
        if company and (company.last_contact_at is None or company.last_contact_at < act.occurred_at):
            company.last_contact_at = act.occurred_at
    return act


def log_field_changes(db: Session, user: User, changes: dict, *, object_type: str, object_id: int, **links) -> None:
    if not changes:
        return
    labels = ", ".join(FIELD_LABELS.get(k, k) for k in changes)
    log_activity(db, type="field_change", title=f"Изменены поля: {labels}", object_type=object_type,
                 object_id=object_id, user=user, meta={"changes": changes}, **links)


def audit(
    db: Session,
    user: User | None,
    action: str,
    summary: str,
    *,
    entity: str | None = None,
    entity_id: int | None = None,
    changes: dict | None = None,
    request: Request | None = None,
) -> None:
    ip = ua = None
    if request is not None:
        from app.core.ratelimit import client_ip

        ip = client_ip(request)
        ua = (request.headers.get("user-agent") or "")[:500]
    db.add(AuditLog(user_id=user.id if user else None, action=action, entity=entity, entity_id=entity_id,
                    summary=summary[:500], changes=changes, ip=ip, user_agent=ua))
