from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require
from app.core.permissions import has_perm
from app.core.security import normalize_phone, phone_hash
from app.db.base import utcnow
from app.db.session import get_db
from app.models import Company, Contact, Deal, User
from app.schemas.common import Page
from app.schemas.crm import BulkAssign, CompanyCreate, CompanyOut, CompanyUpdate
from app.services import access
from app.services.common import apply_sort, clean_custom_fields, ensure_inn, get_setting, paginate
from app.services.journal import apply_changes, audit, log_activity, log_field_changes
from app.services.notify import notify

router = APIRouter(prefix="/companies", tags=["Клиенты: компании"])

SORTABLE = {"name", "created_at", "updated_at", "last_contact_at", "inn", "status"}


def amount_rub(db: Session):
    rates = get_setting(db, "currencies") or {}
    whens = [(Deal.currency == cur, Deal.amount * float(rate)) for cur, rate in rates.items() if cur != "RUB"]
    return case(*whens, else_=Deal.amount) if whens else Deal.amount


def _revenue_subq(db: Session):
    return (select(Deal.company_id, func.coalesce(func.sum(amount_rub(db)), 0).label("revenue"))
            .where(Deal.status == "won", Deal.deleted_at.is_(None)).group_by(Deal.company_id).subquery())


def _open_subq():
    return (select(Deal.company_id, func.count().label("open_deals"))
            .where(Deal.status == "open", Deal.deleted_at.is_(None)).group_by(Deal.company_id).subquery())


def _to_out(company: Company, revenue=0, open_deals=0) -> CompanyOut:
    out = CompanyOut.model_validate(company)
    out.total_revenue = float(revenue or 0)
    out.open_deals = int(open_deals or 0)
    return out


def _dt(d: date, end: bool = False) -> datetime:
    return datetime.combine(d + timedelta(days=1) if end else d, time.min, tzinfo=timezone.utc)


def search_clause(q: str):
    q = q.strip()
    like = f"%{q.lower()}%"
    conds = [func.lower(Company.name).like(like), func.lower(func.coalesce(Company.full_name, "")).like(like),
             Company.inn.like(f"{q}%")]
    if (norm := normalize_phone(q)) and len(norm) >= 6:
        conds.append(Company.phone_hash == phone_hash(q))
        # поиск компании по телефону её контактов
        conds.append(Company.id.in_(select(Contact.company_id).where(
            or_(Contact.phone_mobile_hash == phone_hash(q), Contact.phone_work_hash == phone_hash(q)))))
    conds.append(Company.id.in_(select(Contact.company_id).where(func.lower(Contact.full_name).like(like))))
    return or_(*conds)


@router.get("", response_model=Page[CompanyOut], summary="Список компаний с фильтрами")
def list_companies(
    q: str | None = None,
    industry_id: list[int] = Query(default=[]),
    region_id: list[int] = Query(default=[]),
    client_type_id: list[int] = Query(default=[]),
    status: list[str] = Query(default=[]),
    manager_id: int | None = None,
    source_id: int | None = None,
    revenue_min: float | None = None,
    revenue_max: float | None = None,
    last_contact_from: date | None = None,
    last_contact_to: date | None = None,
    no_contact_days: int | None = Query(default=None, description="Нет контакта более N дней"),
    sort: str | None = None,
    page: int = 1,
    page_size: int = 25,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rev = _revenue_subq(db)
    opn = _open_subq()
    stmt = (select(Company, func.coalesce(rev.c.revenue, 0).label("revenue"),
                   func.coalesce(opn.c.open_deals, 0).label("open_deals"))
            .outerjoin(rev, rev.c.company_id == Company.id).outerjoin(opn, opn.c.company_id == Company.id)
            .where(Company.deleted_at.is_(None)))
    stmt = access.scope_companies(stmt, user)
    if q:
        stmt = stmt.where(search_clause(q))
    if industry_id:
        stmt = stmt.where(Company.industry_id.in_(industry_id))
    if region_id:
        stmt = stmt.where(Company.region_id.in_(region_id))
    if client_type_id:
        stmt = stmt.where(Company.client_type_id.in_(client_type_id))
    if status:
        stmt = stmt.where(Company.status.in_(status))
    if manager_id:
        stmt = stmt.where(Company.manager_id == manager_id)
    if source_id:
        stmt = stmt.where(Company.source_id == source_id)
    if revenue_min is not None:
        stmt = stmt.where(func.coalesce(rev.c.revenue, 0) >= revenue_min)
    if revenue_max is not None:
        stmt = stmt.where(func.coalesce(rev.c.revenue, 0) <= revenue_max)
    if last_contact_from:
        stmt = stmt.where(Company.last_contact_at >= _dt(last_contact_from))
    if last_contact_to:
        stmt = stmt.where(Company.last_contact_at < _dt(last_contact_to, end=True))
    if no_contact_days:
        border = utcnow() - timedelta(days=no_contact_days)
        stmt = stmt.where(or_(Company.last_contact_at.is_(None), Company.last_contact_at < border))

    if sort and sort.lstrip("-") == "revenue":
        col = func.coalesce(rev.c.revenue, 0)
        stmt = stmt.order_by(col.desc() if sort.startswith("-") else col.asc(), Company.id.desc())
    else:
        stmt = apply_sort(stmt, Company, sort, SORTABLE, default="-created_at")

    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.execute(stmt.limit(page_size).offset((page - 1) * page_size)).unique().all()
    return {"items": [_to_out(c, r, o) for c, r, o in rows], "total": total, "page": page, "page_size": page_size,
            "pages": -(-total // page_size)}


@router.get("/check-inn", summary="Проверка дубля по ИНН")
def check_inn(inn: str, exclude_id: int | None = None, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    stmt = select(Company).where(Company.inn == inn, Company.deleted_at.is_(None))
    if exclude_id:
        stmt = stmt.where(Company.id != exclude_id)
    c = db.scalars(stmt).first()
    if c is None:
        return {"exists": False}
    visible = has_perm(user.role, "companies.view_all") or c.manager_id == user.id
    return {"exists": True, "id": c.id if visible else None, "name": c.name,
            "manager": c.manager.full_name if c.manager else None}


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(company_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = access.get_company(db, user, company_id)
    rev = db.scalar(select(func.coalesce(func.sum(amount_rub(db)), 0)).where(
        Deal.company_id == c.id, Deal.status == "won", Deal.deleted_at.is_(None)))
    opn = db.scalar(select(func.count()).select_from(Deal).where(
        Deal.company_id == c.id, Deal.status == "open", Deal.deleted_at.is_(None)))
    return _to_out(c, rev, opn)


def _check_duplicate(db: Session, inn: str | None, exclude_id: int | None = None):
    if not inn:
        return
    ensure_inn(inn)
    stmt = select(Company).where(Company.inn == inn, Company.deleted_at.is_(None))
    if exclude_id:
        stmt = stmt.where(Company.id != exclude_id)
    dup = db.scalars(stmt).first()
    if dup:
        owner = f", ответственный: {dup.manager.full_name}" if dup.manager else ""
        raise HTTPException(409, f"Компания с ИНН {inn} уже есть в базе: «{dup.name}»{owner}")


@router.post("", response_model=CompanyOut, status_code=201)
def create_company(data: CompanyCreate, request: Request, user: User = Depends(require("companies.edit")),
                   db: Session = Depends(get_db)):
    _check_duplicate(db, data.inn)
    values = data.model_dump()
    values["custom_fields"] = clean_custom_fields(db, "company", values.get("custom_fields"))
    if has_perm(user.role, "companies.reassign"):
        values["manager_id"] = values.get("manager_id") or user.id
    else:
        values["manager_id"] = user.id
    c = Company(**values)
    c.phone_hash = phone_hash(c.phone)
    db.add(c)
    db.flush()
    log_activity(db, type="created", title="Компания добавлена в базу", object_type="company", object_id=c.id,
                 user=user, company_id=c.id)
    audit(db, user, "create", f"Создана компания «{c.name}»", entity="company", entity_id=c.id, request=request)
    db.commit()
    return _to_out(c)


@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(company_id: int, data: CompanyUpdate, request: Request,
                   user: User = Depends(require("companies.edit")), db: Session = Depends(get_db)):
    c = access.get_company(db, user, company_id)
    values = data.model_dump(exclude_unset=True)
    if "inn" in values and values["inn"] != c.inn:
        _check_duplicate(db, values["inn"], exclude_id=c.id)
    if "manager_id" in values and values["manager_id"] != c.manager_id and not has_perm(user.role, "companies.reassign"):
        raise HTTPException(403, "Сменить ответственного может только руководитель")
    if "custom_fields" in values:
        values["custom_fields"] = {**(c.custom_fields or {}),
                                   **clean_custom_fields(db, "company", values["custom_fields"], partial=True)}
    changes = apply_changes(c, values)
    if "phone" in changes:
        c.phone_hash = phone_hash(c.phone)
    log_field_changes(db, user, changes, object_type="company", object_id=c.id, company_id=c.id)
    if changes:
        audit(db, user, "update", f"Изменена компания «{c.name}»", entity="company", entity_id=c.id,
              changes=changes, request=request)
    if "manager_id" in changes and c.manager_id and c.manager_id != user.id:
        notify(db, c.manager_id, "Вам передан клиент", c.name, link=f"/companies/{c.id}", kind="assign")
    db.commit()
    return get_company(c.id, user, db)


@router.delete("/{company_id}")
def delete_company(company_id: int, request: Request, user: User = Depends(require("companies.delete")),
                   db: Session = Depends(get_db)):
    c = access.get_company(db, user, company_id)
    c.deleted_at = utcnow()
    audit(db, user, "delete", f"Удалена компания «{c.name}» (ИНН {c.inn or '—'})", entity="company",
          entity_id=c.id, request=request)
    db.commit()
    return {"detail": "Компания удалена"}


@router.post("/bulk-assign", summary="Массовая смена ответственного")
def bulk_assign(data: BulkAssign, request: Request, user: User = Depends(require("companies.reassign")),
                db: Session = Depends(get_db)):
    target = db.get(User, data.user_id)
    if target is None or not target.is_active:
        raise HTTPException(404, "Сотрудник не найден")
    companies = db.scalars(select(Company).where(Company.id.in_(data.ids), Company.deleted_at.is_(None))).unique().all()
    for c in companies:
        if c.manager_id != target.id:
            log_field_changes(db, user, {"manager_id": [c.manager_id, target.id]}, object_type="company",
                              object_id=c.id, company_id=c.id)
            c.manager_id = target.id
    audit(db, user, "bulk_assign", f"{len(companies)} компаний переданы: {target.full_name}", entity="company",
          request=request)
    notify(db, target.id, f"Вам переданы клиенты: {len(companies)}", ", ".join(c.name for c in companies[:5]),
           link="/companies", kind="assign")
    db.commit()
    return {"updated": len(companies)}
