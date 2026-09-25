from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, defaultload, noload

from app.api.deps import get_current_user, require
from app.core.permissions import has_perm
from app.db.base import utcnow
from app.db.session import get_db
from app.models import (
    Activity,
    Company,
    Contact,
    Deal,
    DealContact,
    DealMember,
    DealProduct,
    DealStageHistory,
    DictionaryItem,
    PipelineStage,
    Task,
    User,
)
from app.schemas.common import Page
from app.schemas.crm import BulkAssign, DealCreate, DealDetail, DealMove, DealOut, DealUpdate
from app.services import access
from app.services.common import apply_sort, clean_custom_fields, get_setting, paginate
from app.services.journal import apply_changes, audit, log_activity, log_field_changes
from app.services.notify import notify

router = APIRouter(prefix="/deals", tags=["Сделки"])

SORTABLE = {"created_at", "updated_at", "amount", "close_date", "title", "probability", "stage_changed_at"}

# Для списков и канбана позиции, участники и справочники вложенных компаний/контактов не нужны
LIST_OPTIONS = (
    noload(Deal.products), noload(Deal.contacts), noload(Deal.members),
    defaultload(Deal.company).lazyload("*"), defaultload(Deal.contact).lazyload("*"),
)


def _filtered(
    user: User, q: str | None, stage_id: list[int], status: list[str], owner_id: int | None, company_id: int | None,
    close_from: date | None, close_to: date | None, amount_min: float | None, amount_max: float | None,
    stale: bool,
):
    stmt = access.scope_deals(select(Deal).where(Deal.deleted_at.is_(None)), user)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Deal.title).like(like),
                              Deal.company_id.in_(select(Company.id).where(func.lower(Company.name).like(like)))))
    if stage_id:
        stmt = stmt.where(Deal.stage_id.in_(stage_id))
    if status:
        stmt = stmt.where(Deal.status.in_(status))
    if owner_id:
        stmt = stmt.where(Deal.owner_id == owner_id)
    if company_id:
        stmt = stmt.where(Deal.company_id == company_id)
    if close_from:
        stmt = stmt.where(Deal.close_date >= close_from)
    if close_to:
        stmt = stmt.where(Deal.close_date <= close_to)
    if amount_min is not None:
        stmt = stmt.where(Deal.amount >= amount_min)
    if amount_max is not None:
        stmt = stmt.where(Deal.amount <= amount_max)
    if stale:
        border = utcnow() - timedelta(days=14)
        recent = select(Activity.deal_id).where(Activity.deal_id.is_not(None), Activity.occurred_at >= border)
        planned = select(Task.deal_id).where(Task.deal_id.is_not(None), Task.status == "open")
        stmt = stmt.where(Deal.status == "open", Deal.updated_at < border, Deal.id.not_in(recent),
                          Deal.id.not_in(planned))
    return stmt


@router.get("", response_model=Page[DealOut])
def list_deals(
    q: str | None = None,
    stage_id: list[int] = Query(default=[]),
    status: list[str] = Query(default=[]),
    owner_id: int | None = None,
    company_id: int | None = None,
    close_from: date | None = None,
    close_to: date | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    stale: bool = False,
    sort: str | None = None,
    page: int = 1,
    page_size: int = 25,
    user: User = Depends(require("deals.view")),
    db: Session = Depends(get_db),
):
    stmt = _filtered(user, q, stage_id, status, owner_id, company_id, close_from, close_to, amount_min, amount_max,
                     stale)
    stmt = apply_sort(stmt, Deal, sort, SORTABLE).options(*LIST_OPTIONS)
    return paginate(db, stmt, page, page_size, unique=True)


@router.get("/board", summary="Канбан-доска: сделки по этапам")
def board(
    q: str | None = None,
    owner_id: int | None = None,
    company_id: int | None = None,
    close_from: date | None = None,
    close_to: date | None = None,
    show_closed_days: int = Query(default=30, description="Показывать закрытые сделки за N дней"),
    limit_per_stage: int = 100,
    user: User = Depends(require("deals.view")),
    db: Session = Depends(get_db),
):
    stages = db.scalars(select(PipelineStage).where(PipelineStage.is_active.is_(True))
                        .order_by(PipelineStage.sort)).all()
    rates = get_setting(db, "currencies") or {}
    base = _filtered(user, q, [], [], owner_id, company_id, close_from, close_to, None, None, False)
    base = base.where(or_(Deal.status == "open", Deal.closed_at >= utcnow() - timedelta(days=show_closed_days)))

    # Итоги по этапам — одним агрегирующим запросом
    totals: dict[int, dict] = {}
    for stage_id, currency, cnt, amount in db.execute(
            base.with_only_columns(Deal.stage_id, Deal.currency, func.count(), func.coalesce(func.sum(Deal.amount), 0))
            .group_by(Deal.stage_id, Deal.currency).order_by(None)):
        t = totals.setdefault(stage_id, {"count": 0, "amount": 0.0})
        t["count"] += cnt
        t["amount"] += float(amount) * float(rates.get(currency, 1))

    # Карточки — одним запросом, затем раскладываем по колонкам
    deals = db.scalars(base.options(*LIST_OPTIONS).order_by(Deal.stage_changed_at.desc())).unique().all()
    by_stage: dict[int, list] = {}
    for d in deals:
        bucket = by_stage.setdefault(d.stage_id, [])
        if len(bucket) < limit_per_stage:
            bucket.append(d)

    columns = []
    for s in stages:
        t = totals.get(s.id, {"count": 0, "amount": 0.0})
        columns.append({
            "stage": {"id": s.id, "name": s.name, "color": s.color, "kind": s.kind, "probability": s.probability},
            "count": t["count"],
            "amount": round(t["amount"], 2),
            "weighted": round(t["amount"] * s.probability / 100, 2),
            "deals": [DealOut.model_validate(d).model_dump(mode="json") for d in by_stage.get(s.id, [])],
        })
    return columns


@router.get("/{deal_id}", response_model=DealDetail)
def get_deal(deal_id: int, user: User = Depends(require("deals.view")), db: Session = Depends(get_db)):
    return access.get_deal(db, user, deal_id)


def _set_products(deal: Deal, items) -> None:
    deal.products.clear()
    total = Decimal(0)
    for it in items:
        p = DealProduct(product_id=it.product_id, name=it.name, quantity=it.quantity, unit=it.unit, price=it.price,
                        discount_percent=it.discount_percent)
        deal.products.append(p)
        total += p.total
    if items:
        deal.amount = total


def _set_participants(db: Session, deal: Deal, contacts, members) -> None:
    if contacts is not None:
        deal.contacts.clear()
        db.flush()
        seen = set()
        for c in contacts:
            if c.contact_id in seen or db.get(Contact, c.contact_id) is None:
                continue
            seen.add(c.contact_id)
            deal.contacts.append(DealContact(contact_id=c.contact_id, role=c.role))
    if members is not None:
        deal.members.clear()
        db.flush()
        seen = set()
        for m in members:
            if m.user_id in seen or db.get(User, m.user_id) is None:
                continue
            seen.add(m.user_id)
            deal.members.append(DealMember(user_id=m.user_id, role=m.role))


def _first_stage(db: Session) -> PipelineStage:
    stage = db.scalars(select(PipelineStage).where(PipelineStage.is_active.is_(True), PipelineStage.kind == "open")
                       .order_by(PipelineStage.sort)).first()
    if stage is None:
        raise HTTPException(400, "Не настроены этапы воронки")
    return stage


@router.post("", response_model=DealDetail, status_code=201)
def create_deal(data: DealCreate, request: Request, user: User = Depends(require("deals.edit")),
                db: Session = Depends(get_db)):
    if data.company_id:
        access.get_company(db, user, data.company_id)
    stage = db.get(PipelineStage, data.stage_id) if data.stage_id else _first_stage(db)
    if stage is None:
        raise HTTPException(422, "Этап не найден")
    owner_id = data.owner_id if (data.owner_id and has_perm(user.role, "deals.view_all")) else user.id
    deal = Deal(
        title=data.title, company_id=data.company_id, contact_id=data.contact_id, owner_id=owner_id,
        stage_id=stage.id, amount=data.amount, currency=data.currency,
        probability=data.probability if data.probability is not None else stage.probability,
        close_date=data.close_date or date.today() + timedelta(days=30), description=data.description,
        custom_fields=clean_custom_fields(db, "deal", data.custom_fields), status=stage.kind,
        closed_at=utcnow() if stage.kind != "open" else None,
    )
    db.add(deal)
    db.flush()
    if data.products:
        _set_products(deal, data.products)
    _set_participants(db, deal, data.contacts, data.members)
    db.add(DealStageHistory(deal_id=deal.id, from_stage_id=None, to_stage_id=stage.id, user_id=user.id))
    log_activity(db, type="created", title=f"Создана сделка «{deal.title}»", object_type="deal", object_id=deal.id,
                 user=user, deal_id=deal.id, company_id=deal.company_id, contact_id=deal.contact_id)
    audit(db, user, "create", f"Создана сделка «{deal.title}» на {float(deal.amount):,.0f} {deal.currency}",
          entity="deal", entity_id=deal.id, request=request)
    if owner_id != user.id:
        notify(db, owner_id, "Вам назначена сделка", deal.title, link=f"/deals/{deal.id}", kind="assign")
    db.commit()
    db.refresh(deal)
    return deal


def _move(db: Session, deal: Deal, stage: PipelineStage, user: User, lost_reason_id: int | None = None,
          lost_comment: str | None = None) -> None:
    if stage.id == deal.stage_id:
        return
    if stage.kind == "lost" and not lost_reason_id:
        raise HTTPException(422, "Укажите причину проигрыша сделки")
    now = utcnow()
    prev = deal.stage
    seconds = int((now - deal.stage_changed_at).total_seconds()) if deal.stage_changed_at else None
    db.add(DealStageHistory(deal_id=deal.id, from_stage_id=deal.stage_id, to_stage_id=stage.id, user_id=user.id,
                            seconds_in_prev=seconds))
    deal.stage_id = stage.id
    deal.stage = stage
    deal.stage_changed_at = now
    deal.probability = stage.probability
    deal.status = stage.kind
    if stage.kind == "open":
        deal.closed_at = None
        deal.lost_reason_id = None
        deal.lost_comment = None
    else:
        deal.closed_at = now
        if stage.kind == "lost":
            reason = db.get(DictionaryItem, lost_reason_id)
            deal.lost_reason_id = reason.id if reason else None
            deal.lost_comment = lost_comment
        if deal.company_id and stage.kind == "won":
            company = db.get(Company, deal.company_id)
            if company and company.status == "prospect":
                company.status = "active"
    title = f"Этап: {prev.name if prev else '—'} → {stage.name}"
    if stage.kind == "won":
        title = f"Сделка выиграна 🎉 ({float(deal.amount):,.0f} {deal.currency})".replace(",", " ")
    elif stage.kind == "lost":
        title = "Сделка проиграна"
    log_activity(db, type="stage_change", title=title, body=lost_comment, object_type="deal", object_id=deal.id,
                 user=user, deal_id=deal.id, company_id=deal.company_id,
                 meta={"from": prev.name if prev else None, "to": stage.name})
    if deal.owner_id and deal.owner_id != user.id:
        notify(db, deal.owner_id, f"Сделка перемещена: {stage.name}", deal.title, link=f"/deals/{deal.id}",
               kind="deal", email=False)


@router.patch("/{deal_id}", response_model=DealDetail)
def update_deal(deal_id: int, data: DealUpdate, request: Request, user: User = Depends(require("deals.edit")),
                db: Session = Depends(get_db)):
    deal = access.get_deal(db, user, deal_id)
    values = data.model_dump(exclude_unset=True, exclude={"products", "contacts", "members", "stage_id"})
    if "owner_id" in values and values["owner_id"] != deal.owner_id and not has_perm(user.role, "deals.view_all"):
        raise HTTPException(403, "Сменить ответственного может только руководитель")
    if values.get("company_id"):
        access.get_company(db, user, values["company_id"])
    if "custom_fields" in values:
        values["custom_fields"] = {**(deal.custom_fields or {}),
                                   **clean_custom_fields(db, "deal", values["custom_fields"], partial=True)}
    old_amount = float(deal.amount)
    changes = apply_changes(deal, values)
    if data.products is not None:
        _set_products(deal, data.products)
        if float(deal.amount) != old_amount:
            changes["amount"] = [old_amount, float(deal.amount)]
    _set_participants(db, deal, data.contacts, data.members)
    if data.stage_id and data.stage_id != deal.stage_id:
        stage = db.get(PipelineStage, data.stage_id)
        if stage is None:
            raise HTTPException(422, "Этап не найден")
        _move(db, deal, stage, user)
    log_field_changes(db, user, changes, object_type="deal", object_id=deal.id, deal_id=deal.id,
                      company_id=deal.company_id)
    if changes:
        audit(db, user, "amount_change" if "amount" in changes else "update", f"Изменена сделка «{deal.title}»",
              entity="deal", entity_id=deal.id, changes=changes, request=request)
    if "owner_id" in changes and deal.owner_id:
        notify(db, deal.owner_id, "Вам передана сделка", deal.title, link=f"/deals/{deal.id}", kind="assign")
    deal.updated_at = utcnow()
    db.commit()
    db.refresh(deal)
    return deal


@router.post("/{deal_id}/move", response_model=DealOut, summary="Перенос сделки на другой этап (drag-and-drop)")
def move_deal(deal_id: int, data: DealMove, user: User = Depends(require("deals.edit")),
              db: Session = Depends(get_db)):
    deal = access.get_deal(db, user, deal_id)
    stage = db.get(PipelineStage, data.stage_id)
    if stage is None or not stage.is_active:
        raise HTTPException(422, "Этап не найден")
    _move(db, deal, stage, user, data.lost_reason_id, data.lost_comment)
    deal.updated_at = utcnow()
    db.commit()
    db.refresh(deal)
    return deal


@router.get("/{deal_id}/history", summary="История перемещения по воронке")
def stage_history(deal_id: int, user: User = Depends(require("deals.view")), db: Session = Depends(get_db)):
    access.get_deal(db, user, deal_id)
    stages = {s.id: s.name for s in db.scalars(select(PipelineStage))}
    rows = db.scalars(select(DealStageHistory).where(DealStageHistory.deal_id == deal_id)
                      .order_by(DealStageHistory.changed_at)).all()
    return [{"from": stages.get(r.from_stage_id), "to": stages.get(r.to_stage_id), "changed_at": r.changed_at,
             "days_in_prev": round(r.seconds_in_prev / 86400, 1) if r.seconds_in_prev else None} for r in rows]


@router.post("/bulk-assign", summary="Массово передать сделки другому менеджеру")
def bulk_assign(data: BulkAssign, request: Request, user: User = Depends(require("deals.view_all")),
                db: Session = Depends(get_db)):
    target = db.get(User, data.user_id)
    if target is None or not target.is_active:
        raise HTTPException(404, "Сотрудник не найден")
    deals = db.scalars(select(Deal).where(Deal.id.in_(data.ids), Deal.deleted_at.is_(None))).unique().all()
    for d in deals:
        d.owner_id = target.id
    notify(db, target.id, f"Вам переданы сделки: {len(deals)}", None, link="/deals", kind="assign")
    audit(db, user, "bulk_assign", f"{len(deals)} сделок переданы: {target.full_name}", entity="deal",
          request=request)
    db.commit()
    return {"updated": len(deals)}


@router.delete("/{deal_id}")
def delete_deal(deal_id: int, request: Request, user: User = Depends(require("deals.delete")),
                db: Session = Depends(get_db)):
    deal = access.get_deal(db, user, deal_id)
    deal.deleted_at = utcnow()
    audit(db, user, "delete", f"Удалена сделка «{deal.title}» ({float(deal.amount):,.0f} {deal.currency})",
          entity="deal", entity_id=deal.id, request=request)
    db.commit()
    return {"detail": "Сделка удалена"}
