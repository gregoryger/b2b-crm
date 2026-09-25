"""Единый пересчёт денежных показателей по курсам CRM."""
from decimal import Decimal

from sqlalchemy.orm import Session

from app.services.common import get_setting


def currency_rates(db: Session) -> dict[str, float]:
    return {**{k: float(v) for k, v in (get_setting(db, "currencies") or {}).items()}, "RUB": 1.0}


def to_rubles(amount, currency: str, rates: dict[str, float]) -> float:
    return float(Decimal(str(amount or 0)) * Decimal(str(rates.get(currency or "RUB", 1))))
