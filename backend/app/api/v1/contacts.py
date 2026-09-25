from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require
from app.core.security import normalize_phone, phone_hash
from app.db.base import utcnow
from app.db.session import get_db
from app.models import Contact, User
from app.schemas.common import Page
from app.schemas.crm import ContactCreate, ContactOut, ContactUpdate
from app.services import access
from app.services.common import apply_sort, clean_custom_fields, paginate
from app.services.journal import apply_changes, audit, log_activity, log_field_changes

router = APIRouter(prefix="/contacts", tags=["Клиенты: контакты"])

SORTABLE = {"full_name", "created_at", "position"}


def _full_name(c: Contact) -> str:
    return " ".join(p for p in (c.last_name, c.first_name, c.middle_name) if p)


def _hash_phones(c: Contact) -> None:
    c.phone_mobile_hash = phone_hash(c.phone_mobile)
    c.phone_work_hash = phone_hash(c.phone_work)


@router.get("", response_model=Page[ContactOut])
def list_contacts(
    q: str | None = None,
    company_id: int | None = None,
    role_in_deal: list[str] = Query(default=[]),
    sort: str | None = None,
    page: int = 1,
    page_size: int = 25,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = access.scope_contacts(select(Contact).where(Contact.deleted_at.is_(None)), user)
    if q:
        like = f"%{q.lower()}%"
        conds = [func.lower(Contact.full_name).like(like), func.lower(func.coalesce(Contact.email, "")).like(like),
                 func.lower(func.coalesce(Contact.position, "")).like(like)]
        if (n := normalize_phone(q)) and len(n) >= 6:
            h = phone_hash(q)
            conds += [Contact.phone_mobile_hash == h, Contact.phone_work_hash == h]
        stmt = stmt.where(or_(*conds))
    if company_id:
        stmt = stmt.where(Contact.company_id == company_id)
    if role_in_deal:
        stmt = stmt.where(Contact.role_in_deal.in_(role_in_deal))
    stmt = apply_sort(stmt, Contact, sort, SORTABLE, default="full_name")
    return paginate(db, stmt, page, page_size, unique=True)


@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(contact_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return access.get_contact(db, user, contact_id)


@router.post("", response_model=ContactOut, status_code=201)
def create_contact(data: ContactCreate, request: Request, user: User = Depends(require("companies.edit")),
                   db: Session = Depends(get_db)):
    values = data.model_dump()
    if values.get("company_id"):
        company = access.get_company(db, user, values["company_id"])
        values["owner_id"] = values.get("owner_id") or company.manager_id or user.id
    else:
        values["owner_id"] = values.get("owner_id") or user.id
    values["custom_fields"] = clean_custom_fields(db, "contact", values.get("custom_fields"))
    c = Contact(**values)
    c.full_name = _full_name(c)
    _hash_phones(c)
    db.add(c)
    db.flush()
    log_activity(db, type="created", title=f"Добавлен контакт: {c.full_name}", object_type="contact",
                 object_id=c.id, user=user, contact_id=c.id, company_id=c.company_id)
    audit(db, user, "create", f"Создан контакт «{c.full_name}»", entity="contact", entity_id=c.id, request=request)
    db.commit()
    db.refresh(c)
    return c


@router.patch("/{contact_id}", response_model=ContactOut)
def update_contact(contact_id: int, data: ContactUpdate, request: Request,
                   user: User = Depends(require("companies.edit")), db: Session = Depends(get_db)):
    c = access.get_contact(db, user, contact_id)
    values = data.model_dump(exclude_unset=True)
    if values.get("company_id"):
        access.get_company(db, user, values["company_id"])
    if "custom_fields" in values:
        values["custom_fields"] = {**(c.custom_fields or {}),
                                   **clean_custom_fields(db, "contact", values["custom_fields"], partial=True)}
    changes = apply_changes(c, values)
    c.full_name = _full_name(c)
    _hash_phones(c)
    log_field_changes(db, user, changes, object_type="contact", object_id=c.id, contact_id=c.id,
                      company_id=c.company_id)
    if changes:
        audit(db, user, "update", f"Изменён контакт «{c.full_name}»", entity="contact", entity_id=c.id,
              changes=changes, request=request)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/{contact_id}")
def delete_contact(contact_id: int, request: Request, user: User = Depends(require("companies.edit")),
                   db: Session = Depends(get_db)):
    c = access.get_contact(db, user, contact_id)
    if user.role == "manager" and c.owner_id != user.id:
        raise HTTPException(403, "Удалить можно только свой контакт")
    c.deleted_at = utcnow()
    audit(db, user, "delete", f"Удалён контакт «{c.full_name}»", entity="contact", entity_id=c.id, request=request)
    db.commit()
    return {"detail": "Контакт удалён"}
