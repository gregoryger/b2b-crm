"""Аналитика и отчёты.

Все отчёты возвращают единый формат таблицы {title, columns, rows, totals}, из которого
строятся графики в интерфейсе и выгрузки в PDF / Excel / CSV.
Суммы в разных валютах приводятся к рублям по курсам из системных настроек.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import has_perm
from app.db.base import utcnow
from app.models import (
    Activity,
    Company,
    Deal,
    DealProduct,
    DealStageHistory,
    DictionaryItem,
    Invoice,
    Lead,
    MarketingSpend,
    Payment,
    PipelineStage,
    Product,
    Task,
    User,
)
from app.services.common import get_setting
from app.services.currencies import currency_rates as _rates, to_rubles as _rub

MONTHS_RU = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


@dataclass
class Period:
    date_from: date
    date_to: date

    @property
    def start(self) -> datetime:
        return datetime.combine(self.date_from, time.min, tzinfo=timezone.utc)

    @property
    def end(self) -> datetime:
        return datetime.combine(self.date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)

    @property
    def label(self) -> str:
        return f"{self.date_from:%d.%m.%Y} — {self.date_to:%d.%m.%Y}"


def default_period(kind: str = "month") -> Period:
    today = date.today()
    if kind == "week":
        start = today - timedelta(days=today.weekday())
        return Period(start - timedelta(days=7), start - timedelta(days=1))
    if kind == "prev_month":
        first = today.replace(day=1)
        last_prev = first - timedelta(days=1)
        return Period(last_prev.replace(day=1), last_prev)
    if kind == "year":
        return Period(today.replace(month=1, day=1), today)
    return Period(today.replace(day=1), today)


@dataclass
class Scope:
    """Какие данные попадают в отчёт: менеджер без командных прав видит только себя."""
    owner_id: int | None = None
    source_id: int | None = None
    industry_id: int | None = None
    region_id: int | None = None


def make_scope(user: User, owner_id: int | None = None, **filters) -> Scope:
    if not has_perm(user.role, "analytics.team"):
        owner_id = user.id
    return Scope(owner_id=owner_id, **filters)


def _deal_filters(scope: Scope) -> list:
    conds = [Deal.deleted_at.is_(None)]
    if scope.owner_id:
        conds.append(Deal.owner_id == scope.owner_id)
    if scope.industry_id or scope.region_id:
        sub = select(Company.id)
        if scope.industry_id:
            sub = sub.where(Company.industry_id == scope.industry_id)
        if scope.region_id:
            sub = sub.where(Company.region_id == scope.region_id)
        conds.append(Deal.company_id.in_(sub))
    if scope.source_id:
        conds.append(Deal.lead_id.in_(select(Lead.id).where(Lead.source_id == scope.source_id)))
    return conds


def _lead_filters(scope: Scope) -> list:
    conds = [Lead.deleted_at.is_(None)]
    if scope.owner_id:
        conds.append(Lead.assigned_to == scope.owner_id)
    if scope.source_id:
        conds.append(Lead.source_id == scope.source_id)
    return conds


def _pct(a: float, b: float) -> float:
    return round(a / b * 100, 1) if b else 0.0


# ---------- Сводка / дашборд ----------

def summary(db: Session, period: Period, scope: Scope) -> dict:
    rates = _rates(db)
    dc = _deal_filters(scope)

    won = db.execute(select(Deal.amount, Deal.currency).where(
        *dc, Deal.status == "won", Deal.closed_at >= period.start, Deal.closed_at < period.end)).all()
    revenue = sum(_rub(a, c, rates) for a, c in won)
    lost_count = db.scalar(select(func.count()).select_from(Deal).where(
        *dc, Deal.status == "lost", Deal.closed_at >= period.start, Deal.closed_at < period.end)) or 0

    open_deals = db.execute(select(Deal.amount, Deal.currency, Deal.probability).where(*dc, Deal.status == "open")).all()
    pipeline = sum(_rub(a, c, rates) for a, c, _ in open_deals)
    forecast = sum(_rub(a, c, rates) * p / 100 for a, c, p in open_deals)
    created = db.scalar(select(func.count()).select_from(Deal).where(
        *dc, Deal.created_at >= period.start, Deal.created_at < period.end)) or 0

    lc = _lead_filters(scope)
    leads = db.scalar(select(func.count()).select_from(Lead).where(
        *lc, Lead.created_at >= period.start, Lead.created_at < period.end)) or 0
    leads_converted = db.scalar(select(func.count()).select_from(Lead).where(
        *lc, Lead.created_at >= period.start, Lead.created_at < period.end, Lead.deal_id.is_not(None))) or 0
    response = db.execute(select(Lead.created_at, Lead.first_response_at).where(
        *lc, Lead.created_at >= period.start, Lead.created_at < period.end,
        Lead.first_response_at.is_not(None))).all()
    avg_response_min = (sum((r - c).total_seconds() for c, r in response) / len(response) / 60) if response else 0

    tq = select(func.count()).select_from(Task).where(Task.status == "open", Task.due_at < utcnow())
    if scope.owner_id:
        tq = tq.where(Task.assignee_id == scope.owner_id)
    overdue_tasks = db.scalar(tq) or 0

    pq = select(Payment.amount, Invoice.currency).join(Invoice).where(
        Payment.paid_at >= period.date_from, Payment.paid_at <= period.date_to)
    if scope.owner_id:
        pq = pq.where(Invoice.owner_id == scope.owner_id)
    payments = sum(_rub(a, c, rates) for a, c in db.execute(pq).all())

    return {
        "period": {"from": period.date_from.isoformat(), "to": period.date_to.isoformat()},
        "revenue": round(revenue, 2),
        "won_count": len(won),
        "lost_count": lost_count,
        "win_rate": _pct(len(won), len(won) + lost_count),
        "avg_check": round(revenue / len(won), 2) if won else 0,
        "deals_created": created,
        "open_deals": len(open_deals),
        "pipeline": round(pipeline, 2),
        "forecast": round(forecast, 2),
        "leads": leads,
        "lead_conversion": _pct(leads_converted, leads),
        "avg_lead_response_minutes": round(avg_response_min, 1),
        "overdue_tasks": overdue_tasks,
        "payments": round(payments, 2),
    }


def revenue_by_month(db: Session, scope: Scope, period: Period, months: int = 12) -> list[dict]:
    """Выручка по календарным месяцам: не меньше `months` месяцев, заканчивая концом выбранного периода."""
    rates = _rates(db)
    last = period.date_to.replace(day=1)
    back = last.year * 12 + last.month - 1 - (months - 1)
    first = min(period.date_from.replace(day=1), date(back // 12, back % 12 + 1, 1))
    start = datetime.combine(first, time.min, tzinfo=timezone.utc)
    rows = db.execute(select(Deal.closed_at, Deal.amount, Deal.currency, Deal.status).where(
        *_deal_filters(scope), Deal.status.in_(["won", "lost"]),
        Deal.closed_at >= start, Deal.closed_at < period.end)).all()
    buckets: dict[tuple[int, int], dict] = {}
    m = first
    while m <= period.date_to:
        buckets[(m.year, m.month)] = {"month": f"{MONTHS_RU[m.month - 1]} {m.year % 100:02d}",
                                      "revenue": 0.0, "won": 0, "lost": 0}
        m = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
    for closed_at, amount, cur, status in rows:
        b = buckets.get((closed_at.year, closed_at.month))
        if b is None:
            continue
        if status == "won":
            b["revenue"] += _rub(amount, cur, rates)
            b["won"] += 1
        else:
            b["lost"] += 1
    for b in buckets.values():
        b["revenue"] = round(b["revenue"], 2)
    return list(buckets.values())


def forecast_by_month(db: Session, scope: Scope, months: int = 6) -> list[dict]:
    rates = _rates(db)
    today = date.today()
    rows = db.execute(select(Deal.close_date, Deal.amount, Deal.currency, Deal.probability).where(
        *_deal_filters(scope), Deal.status == "open")).all()
    buckets: dict[tuple[int, int], dict] = {}
    m = today.replace(day=1)
    for _ in range(months):
        buckets[(m.year, m.month)] = {"month": f"{MONTHS_RU[m.month - 1]} {m.year % 100:02d}", "amount": 0.0,
                                      "weighted": 0.0, "count": 0}
        m = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
    first_key = min(buckets)
    for close_date, amount, cur, prob in rows:
        key = (close_date.year, close_date.month) if close_date else first_key
        if key < first_key:
            key = first_key  # просроченные по дате закрытия относим на текущий месяц
        b = buckets.get(key)
        if b is None:
            continue
        v = _rub(amount, cur, rates)
        b["amount"] += v
        b["weighted"] += v * prob / 100
        b["count"] += 1
    for b in buckets.values():
        b["amount"] = round(b["amount"], 2)
        b["weighted"] = round(b["weighted"], 2)
    return list(buckets.values())


def pipeline_by_stage(db: Session, scope: Scope) -> list[dict]:
    """Текущие сделки в работе по этапам — «срез» воронки для дашборда."""
    rates = _rates(db)
    stages = list(db.scalars(select(PipelineStage).where(PipelineStage.is_active.is_(True),
                                                        PipelineStage.kind == "open").order_by(PipelineStage.sort)))
    rows = db.execute(select(Deal.stage_id, Deal.amount, Deal.currency).where(
        *_deal_filters(scope), Deal.status == "open")).all()
    agg: dict[int, list] = defaultdict(lambda: [0, 0.0])
    for stage_id, amount, cur in rows:
        agg[stage_id][0] += 1
        agg[stage_id][1] += _rub(amount, cur, rates)
    return [{"stage": s.name, "color": s.color, "probability": s.probability, "count": agg[s.id][0],
             "amount": round(agg[s.id][1], 2)} for s in stages]


# ---------- Воронка ----------

def funnel(db: Session, period: Period, scope: Scope) -> dict:
    rates = _rates(db)
    stages = list(db.scalars(select(PipelineStage).where(PipelineStage.is_active.is_(True))
                             .order_by(PipelineStage.sort)))
    open_stages = [s for s in stages if s.kind == "open"]
    sort_of = {s.id: s.sort for s in stages}
    max_open_sort = max((s.sort for s in open_stages), default=0)
    open_ids = {s.id for s in open_stages}

    deals = db.execute(select(Deal.id, Deal.stage_id, Deal.status, Deal.amount, Deal.currency).where(
        *_deal_filters(scope), Deal.created_at >= period.start, Deal.created_at < period.end)).all()
    ids = [d.id for d in deals]
    visited: dict[int, set[int]] = defaultdict(set)
    if ids:
        for deal_id, stage_id in db.execute(select(DealStageHistory.deal_id, DealStageHistory.to_stage_id)
                                            .where(DealStageHistory.deal_id.in_(ids))):
            visited[deal_id].add(stage_id)

    reached: dict[int, int] = defaultdict(int)
    reached_amount: dict[int, float] = defaultdict(float)
    for d in deals:
        visited[d.id].add(d.stage_id)
        if d.status == "won":
            depth = max_open_sort
        else:
            depth = max((sort_of[s] for s in visited[d.id] if s in open_ids), default=0)
        for s in open_stages:
            if s.sort <= depth:
                reached[s.id] += 1
                reached_amount[s.id] += _rub(d.amount, d.currency, rates)

    # Среднее время на этапе (по всем переходам за период)
    durations = dict(db.execute(
        select(DealStageHistory.from_stage_id, func.avg(DealStageHistory.seconds_in_prev))
        .where(DealStageHistory.changed_at >= period.start, DealStageHistory.changed_at < period.end,
               DealStageHistory.deal_id.in_(select(Deal.id).where(*_deal_filters(scope))),
               DealStageHistory.seconds_in_prev.is_not(None))
        .group_by(DealStageHistory.from_stage_id)).all())

    current = dict(db.execute(select(Deal.stage_id, func.count()).where(*_deal_filters(scope), Deal.status == "open")
                              .group_by(Deal.stage_id)).all())

    rows = []
    prev = None
    total = len(deals)
    for s in open_stages:
        cnt = reached[s.id]
        rows.append({
            "stage": s.name, "color": s.color, "reached": cnt, "amount": round(reached_amount[s.id], 2),
            "conversion_from_prev": _pct(cnt, prev) if prev is not None else 100.0,
            "conversion_from_start": _pct(cnt, total),
            "avg_days": round(float(durations.get(s.id) or 0) / 86400, 1),
            "current": current.get(s.id, 0),
        })
        prev = cnt
    won = sum(1 for d in deals if d.status == "won")
    lost = sum(1 for d in deals if d.status == "lost")
    rows.append({"stage": "Успех", "color": "green", "reached": won,
                 "amount": round(sum(_rub(d.amount, d.currency, rates) for d in deals if d.status == "won"), 2),
                 "conversion_from_prev": _pct(won, prev or 0), "conversion_from_start": _pct(won, total),
                 "avg_days": None, "current": None})
    return {
        "title": "Воронка продаж",
        "subtitle": f"Сделки, созданные за период {period.label}",
        "columns": [
            {"key": "stage", "label": "Этап", "type": "text"},
            {"key": "reached", "label": "Дошло сделок", "type": "int"},
            {"key": "amount", "label": "Сумма, ₽", "type": "money"},
            {"key": "conversion_from_prev", "label": "Конверсия из пред. этапа, %", "type": "pct"},
            {"key": "conversion_from_start", "label": "Конверсия от начала, %", "type": "pct"},
            {"key": "avg_days", "label": "Ср. время на этапе, дн.", "type": "float"},
            {"key": "current", "label": "Сейчас на этапе", "type": "int"},
        ],
        "rows": rows,
        "totals": {"stage": "Всего сделок", "reached": total, "lost": lost},
    }


# ---------- Эффективность менеджеров ----------

def managers(db: Session, period: Period, scope: Scope) -> dict:
    rates = _rates(db)
    uq = select(User).where(User.role.in_(["manager", "head"]))
    if scope.owner_id:
        uq = select(User).where(User.id == scope.owner_id)
    users = list(db.scalars(uq.order_by(User.full_name)))
    dc = _deal_filters(Scope(industry_id=scope.industry_id, region_id=scope.region_id, source_id=scope.source_id))

    closed = db.execute(select(Deal.owner_id, Deal.status, Deal.amount, Deal.currency).where(
        *dc, Deal.status.in_(["won", "lost"]), Deal.closed_at >= period.start, Deal.closed_at < period.end)).all()
    created = dict(db.execute(select(Deal.owner_id, func.count()).where(
        *dc, Deal.created_at >= period.start, Deal.created_at < period.end).group_by(Deal.owner_id)).all())
    pipeline_rows = db.execute(select(Deal.owner_id, Deal.amount, Deal.currency).where(*dc, Deal.status == "open")).all()
    acts = dict(db.execute(select(Activity.user_id, func.count()).where(
        Activity.type.in_(["call", "meeting", "email_out", "note"]),
        Activity.occurred_at >= period.start, Activity.occurred_at < period.end).group_by(Activity.user_id)).all())
    done = dict(db.execute(select(Task.assignee_id, func.count()).where(
        Task.status == "done", Task.completed_at >= period.start, Task.completed_at < period.end)
        .group_by(Task.assignee_id)).all())
    overdue = dict(db.execute(select(Task.assignee_id, func.count()).where(
        Task.status == "open", Task.due_at < utcnow()).group_by(Task.assignee_id)).all())

    stats: dict[int, dict] = {u.id: {"won": 0, "lost": 0, "revenue": 0.0, "pipeline": 0.0} for u in users}
    for owner, status, amount, cur in closed:
        if owner in stats:
            stats[owner]["won" if status == "won" else "lost"] += 1
            if status == "won":
                stats[owner]["revenue"] += _rub(amount, cur, rates)
    for owner, amount, cur in pipeline_rows:
        if owner in stats:
            stats[owner]["pipeline"] += _rub(amount, cur, rates)

    rows = []
    for u in users:
        s = stats[u.id]
        rows.append({
            "manager": u.full_name, "user_id": u.id, "deals_created": created.get(u.id, 0),
            "won": s["won"], "lost": s["lost"], "win_rate": _pct(s["won"], s["won"] + s["lost"]),
            "revenue": round(s["revenue"], 2), "avg_check": round(s["revenue"] / s["won"], 2) if s["won"] else 0,
            "pipeline": round(s["pipeline"], 2), "activities": acts.get(u.id, 0),
            "tasks_done": done.get(u.id, 0), "tasks_overdue": overdue.get(u.id, 0),
        })
    rows.sort(key=lambda r: r["revenue"], reverse=True)
    return {
        "title": "Эффективность менеджеров",
        "subtitle": f"Период {period.label}",
        "columns": [
            {"key": "manager", "label": "Менеджер", "type": "text"},
            {"key": "deals_created", "label": "Новых сделок", "type": "int"},
            {"key": "won", "label": "Выиграно", "type": "int"},
            {"key": "lost", "label": "Проиграно", "type": "int"},
            {"key": "win_rate", "label": "Win rate, %", "type": "pct"},
            {"key": "revenue", "label": "Выручка, ₽", "type": "money"},
            {"key": "avg_check", "label": "Средний чек, ₽", "type": "money"},
            {"key": "pipeline", "label": "В работе, ₽", "type": "money"},
            {"key": "activities", "label": "Активностей", "type": "int"},
            {"key": "tasks_done", "label": "Задач выполнено", "type": "int"},
            {"key": "tasks_overdue", "label": "Задач просрочено", "type": "int"},
        ],
        "rows": rows,
        "totals": {"manager": "Итого", "revenue": round(sum(r["revenue"] for r in rows), 2),
                   "won": sum(r["won"] for r in rows), "lost": sum(r["lost"] for r in rows),
                   "deals_created": sum(r["deals_created"] for r in rows),
                   "pipeline": round(sum(r["pipeline"] for r in rows), 2)},
    }


# ---------- Источники лидов ----------

def sources(db: Session, period: Period, scope: Scope) -> dict:
    rates = _rates(db)
    items = list(db.scalars(select(DictionaryItem).where(DictionaryItem.kind == "lead_source")
                            .order_by(DictionaryItem.sort, DictionaryItem.name)))
    lc = _lead_filters(scope)
    leads = db.execute(select(Lead.source_id, Lead.status, Lead.deal_id).where(
        *lc, Lead.created_at >= period.start, Lead.created_at < period.end)).all()
    won = db.execute(select(Lead.source_id, Deal.amount, Deal.currency).join(Deal, Deal.lead_id == Lead.id).where(
        *lc, Deal.status == "won", Deal.deleted_at.is_(None),
        Deal.closed_at >= period.start, Deal.closed_at < period.end)).all()
    spend = dict(db.execute(select(MarketingSpend.source_id, func.sum(MarketingSpend.amount)).where(
        MarketingSpend.month >= period.date_from.replace(day=1), MarketingSpend.month <= period.date_to)
        .group_by(MarketingSpend.source_id)).all())

    agg: dict[int | None, dict] = defaultdict(lambda: {"leads": 0, "qualified": 0, "rejected": 0, "deals": 0,
                                                       "won": 0, "revenue": 0.0})
    for src, status, deal_id in leads:
        a = agg[src]
        a["leads"] += 1
        a["qualified"] += status == "qualified"
        a["rejected"] += status == "rejected"
        a["deals"] += deal_id is not None
    for src, amount, cur in won:
        agg[src]["won"] += 1
        agg[src]["revenue"] += _rub(amount, cur, rates)

    rows = []
    names = {i.id: i.name for i in items}
    for src_id in list(names) + ([None] if None in agg else []):
        a = agg[src_id]
        sp = float(spend.get(src_id) or 0)
        if not a["leads"] and not sp and not a["won"]:
            continue
        rows.append({
            "source": names.get(src_id, "Не указан"), "leads": a["leads"], "qualified": a["qualified"],
            "rejected": a["rejected"], "deals": a["deals"], "conversion": _pct(a["deals"], a["leads"]),
            "won": a["won"], "revenue": round(a["revenue"], 2), "spend": round(sp, 2),
            "cpl": round(sp / a["leads"], 2) if a["leads"] else 0,
            "cac": round(sp / a["won"], 2) if a["won"] else 0,
            "roi": _pct(a["revenue"] - sp, sp) if sp else None,
        })
    rows.sort(key=lambda r: r["leads"], reverse=True)
    return {
        "title": "Источники лидов",
        "subtitle": f"Период {period.label}",
        "columns": [
            {"key": "source", "label": "Источник", "type": "text"},
            {"key": "leads", "label": "Лидов", "type": "int"},
            {"key": "qualified", "label": "Квалифицировано", "type": "int"},
            {"key": "rejected", "label": "Отклонено", "type": "int"},
            {"key": "deals", "label": "Сделок", "type": "int"},
            {"key": "conversion", "label": "Конверсия в сделку, %", "type": "pct"},
            {"key": "won", "label": "Продаж", "type": "int"},
            {"key": "revenue", "label": "Выручка, ₽", "type": "money"},
            {"key": "spend", "label": "Бюджет, ₽", "type": "money"},
            {"key": "cpl", "label": "Стоимость лида, ₽", "type": "money"},
            {"key": "cac", "label": "Стоимость продажи, ₽", "type": "money"},
            {"key": "roi", "label": "ROI, %", "type": "pct"},
        ],
        "rows": rows,
        "totals": {"source": "Итого", "leads": sum(r["leads"] for r in rows), "deals": sum(r["deals"] for r in rows),
                   "won": sum(r["won"] for r in rows), "revenue": round(sum(r["revenue"] for r in rows), 2),
                   "spend": round(sum(r["spend"] for r in rows), 2)},
    }


# ---------- Продуктовая аналитика ----------

def products(db: Session, period: Period, scope: Scope) -> dict:
    rates = _rates(db)
    rows_db = db.execute(
        select(DealProduct.product_id, DealProduct.name, DealProduct.quantity, DealProduct.price,
               DealProduct.discount_percent, Deal.currency, Deal.id, Product.cost, Product.category)
        .join(Deal, Deal.id == DealProduct.deal_id).outerjoin(Product, Product.id == DealProduct.product_id)
        .where(*_deal_filters(scope), Deal.status == "won", Deal.closed_at >= period.start,
               Deal.closed_at < period.end)).all()
    agg: dict = defaultdict(lambda: {"qty": 0.0, "revenue": 0.0, "cost": 0.0, "deals": set(), "category": None})
    for pid, name, qty, price, disc, cur, deal_id, cost, category in rows_db:
        key = pid or name
        a = agg[key]
        a["name"] = name
        a["category"] = category
        q = float(qty)
        line = q * float(price) * (1 - float(disc) / 100)
        a["qty"] += q
        a["revenue"] += _rub(line, cur, rates)
        a["cost"] += _rub(q * float(cost or 0), cur, rates)
        a["deals"].add(deal_id)
    rows = []
    for a in agg.values():
        margin = a["revenue"] - a["cost"]
        rows.append({"product": a["name"], "category": a["category"] or "—", "quantity": round(a["qty"], 2),
                     "deals": len(a["deals"]), "revenue": round(a["revenue"], 2), "cost": round(a["cost"], 2),
                     "margin": round(margin, 2), "margin_pct": _pct(margin, a["revenue"])})
    rows.sort(key=lambda r: r["revenue"], reverse=True)
    total_rev = sum(r["revenue"] for r in rows)
    total_margin = sum(r["margin"] for r in rows)
    return {
        "title": "Продуктовая аналитика",
        "subtitle": f"Выигранные сделки за период {period.label}",
        "columns": [
            {"key": "product", "label": "Продукт / услуга", "type": "text"},
            {"key": "category", "label": "Категория", "type": "text"},
            {"key": "quantity", "label": "Кол-во", "type": "float"},
            {"key": "deals", "label": "Сделок", "type": "int"},
            {"key": "revenue", "label": "Выручка, ₽", "type": "money"},
            {"key": "cost", "label": "Себестоимость, ₽", "type": "money"},
            {"key": "margin", "label": "Маржа, ₽", "type": "money"},
            {"key": "margin_pct", "label": "Маржинальность, %", "type": "pct"},
        ],
        "rows": rows,
        "totals": {"product": "Итого", "revenue": round(total_rev, 2), "margin": round(total_margin, 2),
                   "margin_pct": _pct(total_margin, total_rev)},
    }


# ---------- Дебиторская задолженность ----------

def receivables(db: Session, period: Period | None, scope: Scope) -> dict:
    rates = _rates(db)
    q = select(Invoice).where(Invoice.status.in_(["issued", "partially_paid"]))
    if scope.owner_id:
        q = q.where(Invoice.owner_id == scope.owner_id)
    today = date.today()
    rows = []
    buckets = {"current": 0.0, "1_30": 0.0, "31_60": 0.0, "61_90": 0.0, "90_plus": 0.0}
    for inv in db.scalars(q.order_by(Invoice.due_date)):
        debt = _rub(Decimal(inv.amount) - Decimal(inv.paid_amount), inv.currency, rates)
        days = (today - inv.due_date).days
        if days <= 0:
            buckets["current"] += debt
        elif days <= 30:
            buckets["1_30"] += debt
        elif days <= 60:
            buckets["31_60"] += debt
        elif days <= 90:
            buckets["61_90"] += debt
        else:
            buckets["90_plus"] += debt
        rows.append({"invoice": inv.number, "invoice_id": inv.id, "company": inv.company.name if inv.company else "—",
                     "manager": inv.owner.full_name if inv.owner else "—",
                     "issued_at": inv.issued_at.isoformat(), "due_date": inv.due_date.isoformat(),
                     "amount": round(_rub(inv.amount, inv.currency, rates), 2),
                     "paid": round(_rub(inv.paid_amount, inv.currency, rates), 2),
                     "debt": round(debt, 2), "overdue_days": max(days, 0)})
    return {
        "title": "Дебиторская задолженность",
        "subtitle": f"На {today:%d.%m.%Y}",
        "columns": [
            {"key": "invoice", "label": "Счёт", "type": "text"},
            {"key": "company", "label": "Клиент", "type": "text"},
            {"key": "manager", "label": "Менеджер", "type": "text"},
            {"key": "issued_at", "label": "Выставлен", "type": "date"},
            {"key": "due_date", "label": "Срок оплаты", "type": "date"},
            {"key": "amount", "label": "Сумма, ₽", "type": "money"},
            {"key": "paid", "label": "Оплачено, ₽", "type": "money"},
            {"key": "debt", "label": "Долг, ₽", "type": "money"},
            {"key": "overdue_days", "label": "Просрочка, дн.", "type": "int"},
        ],
        "rows": rows,
        "totals": {"invoice": "Итого", "debt": round(sum(r["debt"] for r in rows), 2),
                   "amount": round(sum(r["amount"] for r in rows), 2), "paid": round(sum(r["paid"] for r in rows), 2)},
        "aging": {k: round(v, 2) for k, v in buckets.items()},
    }


# ---------- Конструктор отчётов ----------

METRICS = {
    "revenue": "Выручка, ₽",
    "deals_won": "Выигранные сделки",
    "deals_created": "Новые сделки",
    "leads": "Лиды",
    "activities": "Активности",
    "payments": "Поступления, ₽",
}
GROUPS = {
    "day": "День", "week": "Неделя", "month": "Месяц", "manager": "Менеджер", "source": "Источник",
    "industry": "Отрасль", "region": "Регион", "stage": "Этап",
}


def _bucket(dt: date | datetime, group: str) -> str:
    d = dt.date() if isinstance(dt, datetime) else dt
    if group == "day":
        return d.isoformat()
    if group == "week":
        monday = d - timedelta(days=d.weekday())
        return monday.isoformat()
    return d.replace(day=1).isoformat()[:7]


def custom(db: Session, period: Period, scope: Scope, metric: str, group_by: str) -> dict:
    if metric not in METRICS or group_by not in GROUPS:
        raise ValueError("Неизвестная метрика или группировка")
    rates = _rates(db)
    time_group = group_by in ("day", "week", "month")
    data: dict[str, float] = defaultdict(float)
    names: dict = {}

    def dict_names(kind_ids):
        return {i.id: i.name for i in db.scalars(select(DictionaryItem).where(DictionaryItem.id.in_(kind_ids)))}

    if metric in ("revenue", "deals_won", "deals_created"):
        date_col = Deal.created_at if metric == "deals_created" else Deal.closed_at
        q = (select(Deal, Company.industry_id, Company.region_id, Lead.source_id)
             .outerjoin(Company, Company.id == Deal.company_id).outerjoin(Lead, Lead.id == Deal.lead_id)
             .where(*_deal_filters(scope), date_col >= period.start, date_col < period.end))
        if metric != "deals_created":
            q = q.where(Deal.status == "won")
        rows = db.execute(q).unique().all()
        ids_for_names = set()
        for deal, industry_id, region_id, source_id in rows:
            value = _rub(deal.amount, deal.currency, rates) if metric == "revenue" else 1
            when = deal.created_at if metric == "deals_created" else deal.closed_at
            key = {
                "manager": deal.owner.full_name if deal.owner else "Без ответственного",
                "stage": deal.stage.name, "industry": industry_id, "region": region_id, "source": source_id,
            }.get(group_by) if not time_group else _bucket(when, group_by)
            if group_by in ("industry", "region", "source"):
                ids_for_names.add(key)
            data[key] += value
        if ids_for_names:
            names = dict_names([i for i in ids_for_names if i])
    elif metric == "leads":
        q = select(Lead).where(*_lead_filters(scope), Lead.created_at >= period.start, Lead.created_at < period.end)
        for lead in db.scalars(q).unique():
            if time_group:
                key = _bucket(lead.created_at, group_by)
            elif group_by == "manager":
                key = lead.assignee.full_name if lead.assignee else "Не назначен"
            elif group_by == "source":
                key = lead.source.name if lead.source else "Не указан"
            else:
                key = "—"
            data[key] += 1
    elif metric == "activities":
        q = select(Activity).where(Activity.occurred_at >= period.start, Activity.occurred_at < period.end,
                                   Activity.type.in_(["call", "meeting", "email_out", "email_in", "note"]))
        if scope.owner_id:
            q = q.where(Activity.user_id == scope.owner_id)
        for act in db.scalars(q).unique():
            key = _bucket(act.occurred_at, group_by) if time_group else (
                act.user.full_name if act.user and group_by == "manager" else "—")
            data[key] += 1
    elif metric == "payments":
        q = select(Payment.paid_at, Payment.amount, Invoice.currency, User.full_name).join(Invoice).outerjoin(
            User, User.id == Invoice.owner_id).where(Payment.paid_at >= period.date_from,
                                                     Payment.paid_at <= period.date_to)
        if scope.owner_id:
            q = q.where(Invoice.owner_id == scope.owner_id)
        for paid_at, amount, cur, manager in db.execute(q):
            key = _bucket(paid_at, group_by) if time_group else (manager or "—")
            data[key] += _rub(amount, cur, rates)

    rows = []
    for key, value in data.items():
        label = names.get(key, key) if group_by in ("industry", "region", "source") else key
        rows.append({"group": label if label is not None else "Не указано", "value": round(value, 2)})
    if time_group:
        rows.sort(key=lambda r: r["group"])
    else:
        rows.sort(key=lambda r: r["value"], reverse=True)
    return {
        "title": f"{METRICS[metric]} по: {GROUPS[group_by].lower()}",
        "subtitle": f"Период {period.label}",
        "columns": [{"key": "group", "label": GROUPS[group_by], "type": "text"},
                    {"key": "value", "label": METRICS[metric],
                     "type": "money" if metric in ("revenue", "payments") else "float"}],
        "rows": rows,
        "totals": {"group": "Итого", "value": round(sum(r["value"] for r in rows), 2)},
    }


def build_report(db: Session, name: str, period: Period, scope: Scope) -> dict:
    if name == "funnel":
        return funnel(db, period, scope)
    if name == "managers":
        return managers(db, period, scope)
    if name == "sources":
        return sources(db, period, scope)
    if name == "products":
        return products(db, period, scope)
    if name == "receivables":
        return receivables(db, period, scope)
    if name == "summary":
        s = summary(db, period, scope)
        labels = [
            ("revenue", "Выручка, ₽", "money"), ("won_count", "Выиграно сделок", "int"),
            ("lost_count", "Проиграно сделок", "int"), ("win_rate", "Win rate, %", "pct"),
            ("avg_check", "Средний чек, ₽", "money"), ("deals_created", "Новых сделок", "int"),
            ("open_deals", "Сделок в работе", "int"), ("pipeline", "Сумма в воронке, ₽", "money"),
            ("forecast", "Взвешенный прогноз, ₽", "money"), ("leads", "Новых лидов", "int"),
            ("lead_conversion", "Конверсия лид → сделка, %", "pct"),
            ("avg_lead_response_minutes", "Ср. время реакции на лид, мин", "float"),
            ("payments", "Поступления, ₽", "money"), ("overdue_tasks", "Просроченных задач", "int"),
        ]
        return {
            "title": "Сводный отчёт", "subtitle": f"Период {period.label}",
            "columns": [{"key": "metric", "label": "Показатель", "type": "text"},
                        {"key": "value", "label": "Значение", "type": "float"}],
            "rows": [{"metric": label, "value": s[key], "type": t} for key, label, t in labels],
            "totals": None,
        }
    raise ValueError("Неизвестный отчёт")


def stale_deals(db: Session, days: int = 14) -> list[Deal]:
    """Сделки в работе без активности N дней — кандидаты в «потерянные»."""
    border = utcnow() - timedelta(days=days)
    recent = select(Activity.deal_id).where(Activity.deal_id.is_not(None), Activity.occurred_at >= border)
    planned = select(Task.deal_id).where(Task.deal_id.is_not(None), Task.status == "open")
    return list(db.scalars(select(Deal).where(
        Deal.status == "open", Deal.deleted_at.is_(None), Deal.updated_at < border,
        Deal.id.not_in(recent), Deal.id.not_in(planned))).unique())

