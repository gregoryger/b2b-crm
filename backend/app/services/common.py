"""Общие вспомогательные функции: пагинация, нумерация документов, системные настройки, валидация."""
import math
import re
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import CustomField, NumberSequence, SystemSetting

# ---------- Пагинация ----------


def paginate(db: Session, stmt: Select, page: int, page_size: int, *, unique: bool = False) -> dict:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    result = db.execute(stmt.limit(page_size).offset((page - 1) * page_size)).scalars()
    items = list(result.unique() if unique else result)
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "pages": math.ceil(total / page_size) if total else 0}


def apply_sort(stmt: Select, model: Any, sort: str | None, allowed: set[str], default: str = "-created_at") -> Select:
    sort = sort or default
    desc = sort.startswith("-")
    field = sort.lstrip("-")
    if field not in allowed:
        field = default.lstrip("-")
        desc = default.startswith("-")
    col = getattr(model, field)
    return stmt.order_by(col.desc().nulls_last() if desc else col.asc().nulls_last(), model.id.desc())


# ---------- Нумерация документов ----------

def next_number(db: Session, prefix: str) -> str:
    """КП-2026-0001, СЧ-2026-0001, АКТ-2026-0001 — сквозная нумерация по году."""
    year = date.today().year
    key = f"{prefix}-{year}"
    seq = db.get(NumberSequence, key, with_for_update=True)
    if seq is None:
        seq = NumberSequence(key=key, value=0)
        db.add(seq)
        db.flush()
    seq.value += 1
    return f"{prefix}-{year}-{seq.value:04d}"


# ---------- Системные настройки ----------

DEFAULT_SETTINGS: dict[str, Any] = {
    "company_profile": {
        "name": "ООО «Ваша компания»",
        "full_name": "Общество с ограниченной ответственностью «Ваша компания»",
        "inn": "", "kpp": "", "ogrn": "",
        "address": "", "phone": "", "email": "", "website": "",
        "bank_name": "", "bik": "", "account": "", "corr_account": "",
        "director": "", "accountant": "",
        "logo_key": None,
        "accent_color": "#1c7ed6",
    },
    "lead_distribution": {"mode": "round_robin", "user_ids": [], "last_index": -1},
    "currencies": {"RUB": 1, "USD": 90, "EUR": 98, "CNY": 12.5},
}


def get_setting(db: Session, key: str) -> Any:
    row = db.get(SystemSetting, key)
    default = DEFAULT_SETTINGS.get(key)
    if row is None:
        return default
    if isinstance(default, dict) and isinstance(row.value, dict):
        return {**default, **row.value}
    return row.value


def set_setting(db: Session, key: str, value: Any) -> None:
    row = db.get(SystemSetting, key)
    if row is None:
        db.add(SystemSetting(key=key, value=value))
    else:
        row.value = value


# ---------- Валидация реквизитов ----------

def validate_inn(inn: str | None) -> str | None:
    """Проверка контрольной суммы ИНН (10 цифр — юрлицо, 12 — ИП/физлицо)."""
    if not inn:
        return None
    if not re.fullmatch(r"\d{10}|\d{12}", inn):
        return "ИНН должен состоять из 10 или 12 цифр"
    d = [int(c) for c in inn]

    def check(coefs: list[int], n: int) -> bool:
        return sum(c * x for c, x in zip(coefs, d)) % 11 % 10 == d[n]

    if len(d) == 10:
        ok = check([2, 4, 10, 3, 5, 9, 4, 6, 8], 9)
    else:
        ok = check([7, 2, 4, 10, 3, 5, 9, 4, 6, 8], 10) and check([3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8], 11)
    return None if ok else "Некорректная контрольная сумма ИНН"


def ensure_inn(inn: str | None) -> None:
    err = validate_inn(inn)
    if err:
        raise HTTPException(422, err)


# ---------- Пользовательские поля ----------

def clean_custom_fields(db: Session, entity: str, values: dict | None, *, partial: bool = False) -> dict:
    values = values or {}
    fields = db.scalars(select(CustomField).where(CustomField.entity == entity, CustomField.is_active.is_(True))).all()
    by_key = {f.key: f for f in fields}
    result: dict[str, Any] = {}
    for key, value in values.items():
        f = by_key.get(key)
        if f is None:
            continue
        if value in (None, ""):
            result[key] = None
            continue
        try:
            if f.field_type == "number":
                value = float(value)
            elif f.field_type == "checkbox":
                value = bool(value)
            elif f.field_type == "date":
                value = date.fromisoformat(str(value)[:10]).isoformat()
            elif f.field_type == "select":
                if f.options and value not in f.options:
                    raise ValueError
            else:
                value = str(value)[:2000]
        except (TypeError, ValueError):
            raise HTTPException(422, f"Некорректное значение поля «{f.label}»")
        result[key] = value
    if not partial:
        for f in fields:
            if f.required and result.get(f.key) in (None, ""):
                raise HTTPException(422, f"Заполните обязательное поле «{f.label}»")
    return result
