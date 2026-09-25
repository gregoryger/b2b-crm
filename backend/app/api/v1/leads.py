from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require
from app.core.permissions import has_perm
from app.core.security import normalize_phone, phone_hash
from app.db.base import utcnow
from app.db.session import get_db
from app.models import Company, Contact, Deal, DealStageHistory, DictionaryItem, Lead, PipelineStage, User
from app.schemas.common import Page
from app.schemas.crm import BulkAssign, LeadConvert, LeadCreate, LeadOut, LeadReject, LeadUpdate
from app.services import access
from app.services.common import apply_sort, clean_custom_fields, ensure_inn, paginate
from app.services.journal import apply_changes, audit, log_activity, log_field_changes
from app.services.leads import register_lead
from app.services.notify import notify

router = APIRouter(prefix="/leads", tags=["Лиды"])

SORTABLE = {"created_at", "title", "status", "estimated_amount", "updated_at"}
STATUS_LABELS = {"new": "Новый", "in_progress": "В работе", "qualified": "Квалифицирован", "rejected": "Отклонён"}


def mark_first_response(lead: Lead) -> None:
    if lead.first_response_at is None:
        lead.first_response_at = utcnow()
    if lead.status == "new":
        lead.status = "in_progress"


@router.get("", response_model=Page[LeadOut])
def list_leads(
    q: str | None = None,
    status: list[str] = Query(default=[]),
    source_id: list[int] = Query(default=[]),
    assigned_to: int | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    sort: str | None = None,
    page: int = 1,
    page_size: int = 25,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = access.scope_leads(select(Lead).where(Lead.deleted_at.is_(None)), user)
    if q:
        like = f"%{q.lower()}%"
        conds = [func.lower(Lead.title).like(like), func.lower(func.coalesce(Lead.company_name, "")).like(like),
                 func.lower(func.coalesce(Lead.contact_name, "")).like(like),
                 func.lower(func.coalesce(Lead.email, "")).like(like), Lead.inn.like(f"{q}%")]
        if (n := normalize_phone(q)) and len(n) >= 6:
            conds.append(Lead.phone_hash == phone_hash(q))
        stmt = stmt.where(or_(*conds))
    if status:
        stmt = stmt.where(Lead.status.in_(status))
    if source_id:
        stmt = stmt.where(Lead.source_id.in_(source_id))
    if assigned_to:
        stmt = stmt.where(Lead.assigned_to == assigned_to)
    if created_from:
        stmt = stmt.where(Lead.created_at >= created_from)
    if created_to:
        stmt = stmt.where(Lead.created_at < created_to + timedelta(days=1))
    stmt = apply_sort(stmt, Lead, sort, SORTABLE)
    return paginate(db, stmt, page, page_size, unique=True)


@router.get("/stats", summary="Количество лидов по статусам")
def lead_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = access.scope_leads(select(Lead.status, func.count()).where(Lead.deleted_at.is_(None)), user)
    return dict(db.execute(stmt.group_by(Lead.status)).all())


@router.post("", response_model=LeadOut, status_code=201)
def create_lead(data: LeadCreate, request: Request, user: User = Depends(require("leads.edit")),
                db: Session = Depends(get_db)):
    values = data.model_dump()
    values["custom_fields"] = clean_custom_fields(db, "lead", values.get("custom_fields"))
    if values.get("assigned_to") and not has_perm(user.role, "leads.view_all"):
        values["assigned_to"] = user.id
    lead = register_lead(db, values, source_code=None if values.get("source_id") else "manual", user=user)
    audit(db, user, "create", f"Создан лид «{lead.title}»", entity="lead", entity_id=lead.id, request=request)
    db.commit()
    db.refresh(lead)
    return lead


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return access.get_lead(db, user, lead_id)


@router.get("/{lead_id}/duplicates", summary="Похожие компании и контакты (по ИНН, телефону, email, названию)")
def lead_duplicates(lead_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = access.get_lead(db, user, lead_id)
    conds = []
    if lead.inn:
        conds.append(Company.inn == lead.inn)
    if lead.company_name:
        conds.append(func.lower(Company.name) == lead.company_name.lower().strip())
    companies = db.scalars(select(Company).where(Company.deleted_at.is_(None), or_(*conds)).limit(5)).unique().all() \
        if conds else []
    cconds = []
    if lead.email:
        cconds.append(func.lower(Contact.email) == lead.email.lower())
    if lead.phone_hash:
        cconds += [Contact.phone_mobile_hash == lead.phone_hash, Contact.phone_work_hash == lead.phone_hash]
    contacts = db.scalars(select(Contact).where(Contact.deleted_at.is_(None), or_(*cconds)).limit(5)).unique().all() \
        if cconds else []
    return {
        "companies": [{"id": c.id, "name": c.name, "inn": c.inn,
                       "manager": c.manager.full_name if c.manager else None} for c in companies],
        "contacts": [{"id": c.id, "full_name": c.full_name, "company_id": c.company_id,
                      "company": c.company.name if c.company else None} for c in contacts],
    }


@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(lead_id: int, data: LeadUpdate, request: Request, user: User = Depends(require("leads.edit")),
                db: Session = Depends(get_db)):
    lead = access.get_lead(db, user, lead_id)
    if lead.status in ("qualified", "rejected") and data.status:
        raise HTTPException(400, "Лид уже закрыт")
    values = data.model_dump(exclude_unset=True)
    if "assigned_to" in values and values["assigned_to"] != lead.assigned_to and not has_perm(user.role, "leads.view_all"):
        raise HTTPException(403, "Передать лид может руководитель или маркетолог")
    if "custom_fields" in values:
        values["custom_fields"] = {**(lead.custom_fields or {}),
                                   **clean_custom_fields(db, "lead", values["custom_fields"], partial=True)}
    changes = apply_changes(lead, values)
    if "phone" in changes:
        lead.phone_hash = phone_hash(lead.phone)
    if changes.get("status", [None, None])[1] == "in_progress" and lead.first_response_at is None:
        lead.first_response_at = utcnow()
    log_field_changes(db, user, changes, object_type="lead", object_id=lead.id, lead_id=lead.id)
    if "assigned_to" in changes and lead.assigned_to:
        notify(db, lead.assigned_to, "Вам передан лид", lead.title, link=f"/leads/{lead.id}", kind="lead")
    if changes:
        audit(db, user, "update", f"Изменён лид «{lead.title}»", entity="lead", entity_id=lead.id, changes=changes,
              request=request)
    db.commit()
    db.refresh(lead)
    return lead


@router.post("/{lead_id}/take", response_model=LeadOut, summary="Взять лид в работу")
def take_lead(lead_id: int, user: User = Depends(require("leads.edit")), db: Session = Depends(get_db)):
    lead = access.get_lead(db, user, lead_id)
    if lead.status != "new":
        raise HTTPException(400, "Лид уже в работе или закрыт")
    if lead.assigned_to is None:
        lead.assigned_to = user.id
    mark_first_response(lead)
    log_activity(db, type="status_change", title="Лид взят в работу", object_type="lead", object_id=lead.id,
                 user=user, lead_id=lead.id)
    db.commit()
    db.refresh(lead)
    return lead


@router.post("/{lead_id}/reject", response_model=LeadOut, summary="Отклонить лид с указанием причины")
def reject_lead(lead_id: int, data: LeadReject, request: Request, user: User = Depends(require("leads.edit")),
                db: Session = Depends(get_db)):
    lead = access.get_lead(db, user, lead_id)
    if lead.status in ("qualified", "rejected"):
        raise HTTPException(400, "Лид уже закрыт")
    reason = db.get(DictionaryItem, data.reason_id)
    if reason is None or reason.kind != "loss_reason":
        raise HTTPException(422, "Укажите причину отказа из справочника")
    if lead.first_response_at is None:
        lead.first_response_at = utcnow()
    lead.status = "rejected"
    lead.reject_reason_id = reason.id
    lead.reject_comment = data.comment
    log_activity(db, type="status_change", title=f"Лид отклонён: {reason.name}", body=data.comment,
                 object_type="lead", object_id=lead.id, user=user, lead_id=lead.id)
    audit(db, user, "lead_reject", f"Отклонён лид «{lead.title}»: {reason.name}", entity="lead", entity_id=lead.id,
          request=request)
    db.commit()
    db.refresh(lead)
    return lead


def _split_name(full: str | None) -> tuple[str, str, str | None]:
    parts = (full or "").split()
    if not parts:
        return "Контакт", "Без имени", None
    if len(parts) == 1:
        return parts[0], "—", None
    if len(parts) == 2:
        # «Иван Петров» или «Петров Иван» — считаем, что фамилия первая (так чаще пишут в B2B-заявках)
        return parts[0], parts[1], None
    return parts[0], parts[1], " ".join(parts[2:])


@router.post("/{lead_id}/convert", summary="Конвертация: Лид → Сделка + Компания + Контакт в один клик")
def convert_lead(lead_id: int, data: LeadConvert, request: Request, user: User = Depends(require("deals.edit")),
                 db: Session = Depends(get_db)):
    lead = access.get_lead(db, user, lead_id)
    if lead.status in ("qualified", "rejected") or lead.deal_id:
        raise HTTPException(400, "Лид уже закрыт")
    owner_id = lead.assigned_to or user.id

    # 1. Компания: существующая или новая
    if data.company_id:
        company = db.get(Company, data.company_id)
        if company is None or company.deleted_at:
            raise HTTPException(404, "Компания не найдена")
    else:
        inn = data.inn or lead.inn
        if inn:
            ensure_inn(inn)
            existing = db.scalars(select(Company).where(Company.inn == inn, Company.deleted_at.is_(None))).first()
            if existing:
                raise HTTPException(409, f"Компания с ИНН {inn} уже есть: «{existing.name}». Выберите её при конвертации")
        company = Company(name=(data.company_name or lead.company_name or lead.title)[:255], inn=inn,
                          manager_id=owner_id, source_id=lead.source_id, status="prospect",
                          email=None, custom_fields={})
        db.add(company)
        db.flush()
        log_activity(db, type="created", title="Компания создана из лида", object_type="company",
                     object_id=company.id, user=user, company_id=company.id, lead_id=lead.id)

    # 2. Контакт
    contact = None
    if data.contact_id:
        contact = db.get(Contact, data.contact_id)
    elif data.create_contact and (lead.contact_name or lead.phone or lead.email):
        last, first, middle = _split_name(lead.contact_name)
        contact = Contact(company_id=company.id, owner_id=owner_id, last_name=last, first_name=first,
                          middle_name=middle, full_name=" ".join(p for p in (last, first, middle) if p),
                          position=lead.contact_position, phone_mobile=lead.phone, phone_mobile_hash=lead.phone_hash,
                          email=lead.email, custom_fields={})
        db.add(contact)
        db.flush()
    elif lead.contact_id:
        contact = db.get(Contact, lead.contact_id)

    # 3. Сделка на первом этапе воронки
    stage = db.get(PipelineStage, data.stage_id) if data.stage_id else db.scalars(
        select(PipelineStage).where(PipelineStage.is_active.is_(True), PipelineStage.kind == "open")
        .order_by(PipelineStage.sort)).first()
    if stage is None:
        raise HTTPException(400, "Не настроены этапы воронки")
    amount = data.amount or float(lead.estimated_amount or 0)
    deal = Deal(title=(data.deal_title or lead.title)[:255], company_id=company.id,
                contact_id=contact.id if contact else None, lead_id=lead.id, owner_id=owner_id, stage_id=stage.id,
                amount=amount, probability=stage.probability, close_date=data.close_date or (date.today() + timedelta(days=30)),
                custom_fields={})
    db.add(deal)
    db.flush()
    db.add(DealStageHistory(deal_id=deal.id, from_stage_id=None, to_stage_id=stage.id, user_id=user.id))

    lead.status = "qualified"
    lead.qualified_at = utcnow()
    if lead.first_response_at is None:
        lead.first_response_at = lead.qualified_at
    lead.company_id = company.id
    lead.contact_id = contact.id if contact else None
    lead.deal_id = deal.id
    log_activity(db, type="converted", title=f"Лид конвертирован в сделку «{deal.title}»", object_type="deal",
                 object_id=deal.id, user=user, deal_id=deal.id, company_id=company.id, lead_id=lead.id,
                 contact_id=contact.id if contact else None, body=lead.message, touch_company=True)
    audit(db, user, "lead_convert", f"Лид «{lead.title}» → сделка #{deal.id}", entity="lead", entity_id=lead.id,
          request=request)
    db.commit()
    return {"deal_id": deal.id, "company_id": company.id, "contact_id": contact.id if contact else None}


@router.post("/bulk-assign", summary="Массово назначить ответственного")
def bulk_assign(data: BulkAssign, request: Request, user: User = Depends(require("leads.view_all")),
                db: Session = Depends(get_db)):
    target = db.get(User, data.user_id)
    if target is None or not target.is_active:
        raise HTTPException(404, "Сотрудник не найден")
    leads = db.scalars(select(Lead).where(Lead.id.in_(data.ids), Lead.deleted_at.is_(None))).unique().all()
    for lead in leads:
        lead.assigned_to = target.id
    notify(db, target.id, f"Вам назначены лиды: {len(leads)}", None, link="/leads", kind="lead")
    audit(db, user, "bulk_assign", f"{len(leads)} лидов назначены: {target.full_name}", entity="lead", request=request)
    db.commit()
    return {"updated": len(leads)}


@router.delete("/{lead_id}")
def delete_lead(lead_id: int, request: Request, user: User = Depends(require("leads.delete")),
                db: Session = Depends(get_db)):
    lead = access.get_lead(db, user, lead_id)
    lead.deleted_at = utcnow()
    audit(db, user, "delete", f"Удалён лид «{lead.title}»", entity="lead", entity_id=lead.id, request=request)
    db.commit()
    return {"detail": "Лид удалён"}
