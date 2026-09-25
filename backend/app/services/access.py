"""Ограничение видимости данных по ролям («менеджер видит только своё»)."""
from fastapi import HTTPException, status
from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.core.permissions import has_perm
from app.models import Company, Contact, Deal, DealMember, Invoice, Lead, Proposal, Task, User


def scope_companies(stmt: Select, user: User) -> Select:
    if has_perm(user.role, "companies.view_all"):
        return stmt
    return stmt.where(Company.manager_id == user.id)


def scope_contacts(stmt: Select, user: User) -> Select:
    if has_perm(user.role, "companies.view_all"):
        return stmt
    own_companies = select(Company.id).where(Company.manager_id == user.id)
    return stmt.where(or_(Contact.owner_id == user.id, Contact.company_id.in_(own_companies)))


def scope_leads(stmt: Select, user: User) -> Select:
    if has_perm(user.role, "leads.view_all"):
        return stmt
    return stmt.where(Lead.assigned_to == user.id)


def _deal_visible_clause(user: User):
    member_deals = select(DealMember.deal_id).where(DealMember.user_id == user.id)
    return or_(Deal.owner_id == user.id, Deal.id.in_(member_deals))


def scope_deals(stmt: Select, user: User) -> Select:
    if has_perm(user.role, "deals.view_all"):
        return stmt
    if not has_perm(user.role, "deals.view"):
        return stmt.where(False)
    return stmt.where(_deal_visible_clause(user))


def scope_tasks(stmt: Select, user: User) -> Select:
    if has_perm(user.role, "tasks.view_all"):
        return stmt
    return stmt.where(or_(Task.assignee_id == user.id, Task.author_id == user.id))


def scope_proposals(stmt: Select, user: User) -> Select:
    if has_perm(user.role, "deals.view_all"):
        return stmt
    return stmt.where(Proposal.owner_id == user.id)


def scope_invoices(stmt: Select, user: User) -> Select:
    if has_perm(user.role, "deals.view_all"):
        return stmt
    return stmt.where(Invoice.owner_id == user.id)


def _not_found(what: str):
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} не найден(а)")


def get_company(db: Session, user: User, company_id: int) -> Company:
    stmt = scope_companies(select(Company).where(Company.id == company_id, Company.deleted_at.is_(None)), user)
    obj = db.scalars(stmt).first()
    if obj is None:
        raise _not_found("Компания")
    return obj


def get_contact(db: Session, user: User, contact_id: int) -> Contact:
    stmt = scope_contacts(select(Contact).where(Contact.id == contact_id, Contact.deleted_at.is_(None)), user)
    obj = db.scalars(stmt).first()
    if obj is None:
        raise _not_found("Контакт")
    return obj


def get_lead(db: Session, user: User, lead_id: int) -> Lead:
    stmt = scope_leads(select(Lead).where(Lead.id == lead_id, Lead.deleted_at.is_(None)), user)
    obj = db.scalars(stmt).first()
    if obj is None:
        raise _not_found("Лид")
    return obj


def get_deal(db: Session, user: User, deal_id: int) -> Deal:
    stmt = scope_deals(select(Deal).where(Deal.id == deal_id, Deal.deleted_at.is_(None)), user)
    obj = db.scalars(stmt).first()
    if obj is None:
        raise _not_found("Сделка")
    return obj


def get_task(db: Session, user: User, task_id: int) -> Task:
    obj = db.scalars(scope_tasks(select(Task).where(Task.id == task_id), user)).first()
    if obj is None:
        raise _not_found("Задача")
    return obj


def get_proposal(db: Session, user: User, proposal_id: int) -> Proposal:
    obj = db.scalars(scope_proposals(select(Proposal).where(Proposal.id == proposal_id), user)).first()
    if obj is None:
        raise _not_found("КП")
    return obj


def get_invoice(db: Session, user: User, invoice_id: int) -> Invoice:
    obj = db.scalars(scope_invoices(select(Invoice).where(Invoice.id == invoice_id), user)).first()
    if obj is None:
        raise _not_found("Счёт")
    return obj
