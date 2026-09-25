"""Счета, оплаты, акты, дебиторская задолженность и выгрузка в 1С."""
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import quote
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require
from app.db.base import utcnow
from app.db.session import get_db
from app.models import Act, Company, Invoice, Payment, User
from app.schemas.common import Page
from app.schemas.documents import (
    ActCreate,
    ActOut,
    ActUpdate,
    InvoiceCreate,
    InvoiceDetail,
    InvoiceOut,
    InvoiceUpdate,
    PaymentIn,
)
from app.services import access
from app.services.common import get_setting, next_number, paginate
from app.services.documents import act_pdf, invoice_pdf
from app.services.journal import audit, log_activity
from app.services.money import calc_lines
from app.services.notify import notify

router = APIRouter(tags=["Финансы: счета, оплаты, акты"])


def _inv_out(inv: Invoice, detail: bool = False):
    out = (InvoiceDetail if detail else InvoiceOut).model_validate(inv)
    out.debt = round(float(inv.amount) - float(inv.paid_amount), 2) if inv.status != "canceled" else 0
    out.is_overdue = inv.status in ("issued", "partially_paid") and inv.due_date < date.today()
    return out


def _line_dict(it) -> dict:
    return {"product_id": it.product_id, "name": it.name, "quantity": float(it.quantity), "unit": it.unit,
            "price": float(it.price), "discount_percent": float(it.discount_percent)}


@router.get("/invoices", response_model=Page[InvoiceOut])
def list_invoices(
    q: str | None = None,
    status: list[str] = Query(default=[]),
    overdue: bool = False,
    deal_id: int | None = None,
    company_id: int | None = None,
    page: int = 1,
    page_size: int = 25,
    user: User = Depends(require("finance.view")),
    db: Session = Depends(get_db),
):
    stmt = access.scope_invoices(select(Invoice), user)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Invoice.number).like(like),
                              Invoice.company_id.in_(select(Company.id).where(func.lower(Company.name).like(like)))))
    if status:
        stmt = stmt.where(Invoice.status.in_(status))
    if overdue:
        stmt = stmt.where(Invoice.status.in_(["issued", "partially_paid"]), Invoice.due_date < date.today())
    if deal_id:
        stmt = stmt.where(Invoice.deal_id == deal_id)
    if company_id:
        stmt = stmt.where(Invoice.company_id == company_id)
    res = paginate(db, stmt.order_by(Invoice.issued_at.desc(), Invoice.id.desc()), page, page_size, unique=True)
    res["items"] = [_inv_out(i) for i in res["items"]]
    return res


@router.get("/invoices/summary", summary="Сводка по дебиторской задолженности")
def invoices_summary(user: User = Depends(require("finance.view")), db: Session = Depends(get_db)):
    stmt = access.scope_invoices(select(Invoice).where(Invoice.status.in_(["issued", "partially_paid"])), user)
    today = date.today()
    total = overdue = 0.0
    overdue_count = 0
    for inv in db.scalars(stmt).unique():
        debt = float(inv.amount) - float(inv.paid_amount)
        total += debt
        if inv.due_date < today:
            overdue += debt
            overdue_count += 1
    month_start = today.replace(day=1)
    pq = select(func.coalesce(func.sum(Payment.amount), 0)).join(Invoice).where(Payment.paid_at >= month_start)
    if user.role == "manager":
        pq = pq.where(Invoice.owner_id == user.id)
    return {"receivable": round(total, 2), "overdue": round(overdue, 2), "overdue_count": overdue_count,
            "paid_this_month": float(db.scalar(pq) or 0)}


@router.post("/invoices", response_model=InvoiceDetail, status_code=201, summary="Выставить счёт")
def create_invoice(data: InvoiceCreate, request: Request, user: User = Depends(require("finance.edit")),
                   db: Session = Depends(get_db)):
    deal = access.get_deal(db, user, data.deal_id) if data.deal_id else None
    proposal = access.get_proposal(db, user, data.proposal_id) if data.proposal_id else None
    company_id = data.company_id or (deal.company_id if deal else None) or (proposal.company_id if proposal else None)
    if not company_id:
        raise HTTPException(422, "Укажите клиента")
    access.get_company(db, user, company_id)
    if data.items:
        items = [it.model_dump() for it in data.items]
    elif proposal:
        items = [_line_dict(i) for i in proposal.items]
    elif deal and deal.products:
        items = [_line_dict(i) for i in deal.products]
    elif deal:
        items = [{"name": deal.title, "quantity": 1, "unit": "усл.", "price": float(deal.amount),
                  "discount_percent": 0}]
    else:
        raise HTTPException(422, "Добавьте позиции счёта")
    calc = calc_lines(items, data.vat_rate)
    issued = data.issued_at or date.today()
    inv = Invoice(number=next_number(db, "СЧ"), deal_id=deal.id if deal else None, company_id=company_id,
                  owner_id=deal.owner_id if deal and deal.owner_id else user.id, issued_at=issued,
                  due_date=data.due_date or issued + timedelta(days=5), currency=data.currency, vat_rate=data.vat_rate,
                  items=[{k: v for k, v in line.items() if k != "n"} for line in calc["lines"]], amount=calc["total"],
                  paid_amount=0, status="issued", comment=data.comment)
    db.add(inv)
    db.flush()
    log_activity(db, type="invoice", title=f"Выставлен счёт {inv.number} на {float(inv.amount):,.2f} ₽".replace(",", " "),
                 object_type="deal" if deal else "company", object_id=deal.id if deal else company_id, user=user,
                 deal_id=inv.deal_id, company_id=company_id, meta={"invoice_id": inv.id})
    audit(db, user, "invoice_create", f"Выставлен счёт {inv.number}", entity="invoice", entity_id=inv.id,
          request=request)
    db.commit()
    db.refresh(inv)
    return _inv_out(inv, True)


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetail)
def get_invoice(invoice_id: int, user: User = Depends(require("finance.view")), db: Session = Depends(get_db)):
    return _inv_out(access.get_invoice(db, user, invoice_id), True)


@router.patch("/invoices/{invoice_id}", response_model=InvoiceDetail)
def update_invoice(invoice_id: int, data: InvoiceUpdate, request: Request, user: User = Depends(require("finance.edit")),
                   db: Session = Depends(get_db)):
    inv = access.get_invoice(db, user, invoice_id)
    values = data.model_dump(exclude_unset=True)
    if values.get("status") == "canceled":
        if inv.payments:
            raise HTTPException(400, "По счёту есть оплаты — отмена невозможна")
        audit(db, user, "invoice_cancel", f"Отменён счёт {inv.number}", entity="invoice", entity_id=inv.id,
              request=request)
    for k, v in values.items():
        setattr(inv, k, v)
    db.commit()
    db.refresh(inv)
    return _inv_out(inv, True)


def _recalc(inv: Invoice) -> None:
    paid = sum((Decimal(p.amount) for p in inv.payments), Decimal(0))
    inv.paid_amount = paid
    if paid <= 0:
        inv.status, inv.paid_at = "issued", None
    elif paid < Decimal(inv.amount):
        inv.status, inv.paid_at = "partially_paid", None
    else:
        inv.status = "paid"
        inv.paid_at = max(p.paid_at for p in inv.payments)


@router.post("/invoices/{invoice_id}/payments", response_model=InvoiceDetail, summary="Зафиксировать оплату")
def add_payment(invoice_id: int, data: PaymentIn, request: Request, user: User = Depends(require("finance.edit")),
                db: Session = Depends(get_db)):
    inv = access.get_invoice(db, user, invoice_id)
    if inv.status == "canceled":
        raise HTTPException(400, "Счёт отменён")
    debt = Decimal(inv.amount) - Decimal(inv.paid_amount)
    if Decimal(str(data.amount)) > debt + Decimal("0.01"):
        raise HTTPException(422, f"Сумма оплаты больше остатка долга ({float(debt):.2f})")
    inv.payments.append(Payment(amount=data.amount, paid_at=data.paid_at, comment=data.comment, created_by=user.id))
    _recalc(inv)
    log_activity(db, type="payment", title=f"Оплата по счёту {inv.number}: {data.amount:,.2f} ₽".replace(",", " "),
                 object_type="deal" if inv.deal_id else "company", object_id=inv.deal_id or inv.company_id or 0,
                 user=user, deal_id=inv.deal_id, company_id=inv.company_id, meta={"invoice_id": inv.id})
    audit(db, user, "payment_add", f"Оплата {data.amount} по счёту {inv.number}", entity="invoice", entity_id=inv.id,
          request=request)
    if inv.status == "paid" and inv.owner_id and inv.owner_id != user.id:
        notify(db, inv.owner_id, f"Счёт {inv.number} оплачен", inv.company.name if inv.company else None,
               link=f"/finance?invoice={inv.id}", kind="payment")
    db.commit()
    db.refresh(inv)
    return _inv_out(inv, True)


@router.delete("/invoices/{invoice_id}/payments/{payment_id}", response_model=InvoiceDetail)
def delete_payment(invoice_id: int, payment_id: int, request: Request, user: User = Depends(require("finance.edit")),
                   db: Session = Depends(get_db)):
    inv = access.get_invoice(db, user, invoice_id)
    pay = next((p for p in inv.payments if p.id == payment_id), None)
    if pay is None:
        raise HTTPException(404, "Оплата не найдена")
    inv.payments.remove(pay)
    _recalc(inv)
    audit(db, user, "payment_delete", f"Удалена оплата {float(pay.amount)} по счёту {inv.number}", entity="invoice",
          entity_id=inv.id, request=request)
    db.commit()
    db.refresh(inv)
    return _inv_out(inv, True)


@router.get("/invoices/{invoice_id}/pdf")
def invoice_pdf_view(invoice_id: int, download: bool = False, user: User = Depends(require("finance.view")),
                     db: Session = Depends(get_db)):
    inv = access.get_invoice(db, user, invoice_id)
    disp = "attachment" if download else "inline"
    return Response(invoice_pdf(db, inv), media_type="application/pdf",
                    headers={"Content-Disposition": f"{disp}; filename*=UTF-8''{quote(inv.number)}.pdf"})


# ---------- Акты ----------

@router.get("/acts", response_model=Page[ActOut])
def list_acts(company_id: int | None = None, deal_id: int | None = None, page: int = 1, page_size: int = 25,
              user: User = Depends(require("finance.view")), db: Session = Depends(get_db)):
    stmt = select(Act)
    if user.role == "manager":
        stmt = stmt.where(Act.invoice_id.in_(select(Invoice.id).where(Invoice.owner_id == user.id)))
    if company_id:
        stmt = stmt.where(Act.company_id == company_id)
    if deal_id:
        stmt = stmt.where(Act.deal_id == deal_id)
    return paginate(db, stmt.order_by(Act.act_date.desc(), Act.id.desc()), page, page_size, unique=True)


@router.post("/acts", response_model=ActOut, status_code=201, summary="Сформировать акт по счёту")
def create_act(data: ActCreate, request: Request, user: User = Depends(require("finance.edit")),
               db: Session = Depends(get_db)):
    inv = access.get_invoice(db, user, data.invoice_id)
    if inv.status == "canceled":
        raise HTTPException(400, "Счёт отменён")
    act = Act(number=next_number(db, "АКТ"), invoice_id=inv.id, deal_id=inv.deal_id, company_id=inv.company_id,
              act_date=data.act_date or date.today(), amount=inv.amount, vat_rate=inv.vat_rate, items=inv.items,
              status="draft")
    db.add(act)
    db.flush()
    audit(db, user, "act_create", f"Сформирован акт {act.number} по счёту {inv.number}", entity="act",
          entity_id=act.id, request=request)
    db.commit()
    db.refresh(act)
    return act


def _get_act(db: Session, user: User, act_id: int) -> Act:
    act = db.get(Act, act_id)
    if act is None:
        raise HTTPException(404, "Акт не найден")
    if act.invoice_id:
        access.get_invoice(db, user, act.invoice_id)
    return act


@router.patch("/acts/{act_id}", response_model=ActOut)
def update_act(act_id: int, data: ActUpdate, user: User = Depends(require("finance.edit")),
               db: Session = Depends(get_db)):
    act = _get_act(db, user, act_id)
    act.status = data.status
    db.commit()
    db.refresh(act)
    return act


@router.get("/acts/{act_id}/pdf")
def act_pdf_view(act_id: int, download: bool = False, user: User = Depends(require("finance.view")),
                 db: Session = Depends(get_db)):
    act = _get_act(db, user, act_id)
    disp = "attachment" if download else "inline"
    return Response(act_pdf(db, act), media_type="application/pdf",
                    headers={"Content-Disposition": f"{disp}; filename*=UTF-8''{quote(act.number)}.pdf"})


# ---------- Выгрузка в 1С ----------

@router.get("/integrations/1c/export", tags=["Интеграции"],
            summary="Выгрузка счетов и актов в XML для загрузки в 1С (обработка «Загрузка из CRM»)")
def export_1c(date_from: date, date_to: date, only_new: bool = True, request: Request = None,
              user: User = Depends(require("finance.edit")), db: Session = Depends(get_db)):
    profile = get_setting(db, "company_profile")
    inv_q = select(Invoice).where(Invoice.issued_at >= date_from, Invoice.issued_at <= date_to,
                                  Invoice.status != "canceled")
    act_q = select(Act).where(Act.act_date >= date_from, Act.act_date <= date_to)
    if only_new:
        inv_q = inv_q.where(Invoice.exported_1c_at.is_(None))
        act_q = act_q.where(Act.exported_1c_at.is_(None))
    invoices = db.scalars(inv_q).unique().all()
    acts = db.scalars(act_q).unique().all()

    root = ET.Element("ОбменCRM", {"ВерсияФормата": "1.0", "ДатаВыгрузки": utcnow().isoformat(timespec="seconds"),
                                   "Организация": profile.get("name", ""), "ИНН": profile.get("inn", "")})
    clients = ET.SubElement(root, "Контрагенты")
    seen: set[int] = set()

    def add_client(c: Company | None):
        if c is None or c.id in seen:
            return
        seen.add(c.id)
        ET.SubElement(clients, "Контрагент", {
            "Ид": str(c.id), "Наименование": c.name, "ПолноеНаименование": c.full_name or c.name,
            "ИНН": c.inn or "", "КПП": c.kpp or "", "ОГРН": c.ogrn or "", "ЮрАдрес": c.legal_address or "",
            "Банк": c.bank_name or "", "БИК": c.bik or "", "РасчетныйСчет": c.account or ""})

    def add_lines(parent, items):
        rows = ET.SubElement(parent, "Товары")
        for it in items or []:
            q = Decimal(str(it.get("quantity", 1)))
            price = Decimal(str(it.get("price", 0))) * (1 - Decimal(str(it.get("discount_percent", 0))) / 100)
            ET.SubElement(rows, "Строка", {"Наименование": it.get("name", ""), "Количество": str(q),
                                           "ЕдиницаИзмерения": it.get("unit", "шт."),
                                           "Цена": f"{price:.2f}", "Сумма": f"{q * price:.2f}"})

    docs = ET.SubElement(root, "Документы")
    for inv in invoices:
        add_client(inv.company)
        el = ET.SubElement(docs, "СчетНаОплату", {
            "Ид": f"inv-{inv.id}", "Номер": inv.number, "Дата": inv.issued_at.isoformat(),
            "СрокОплаты": inv.due_date.isoformat(), "КонтрагентИд": str(inv.company_id or ""),
            "Валюта": inv.currency, "СтавкаНДС": str(inv.vat_rate), "Сумма": f"{Decimal(inv.amount):.2f}",
            "Оплачено": f"{Decimal(inv.paid_amount):.2f}", "Статус": inv.status})
        add_lines(el, inv.items)
        inv.exported_1c_at = utcnow()
    for act in acts:
        add_client(act.company)
        el = ET.SubElement(docs, "АктВыполненныхРабот", {
            "Ид": f"act-{act.id}", "Номер": act.number, "Дата": act.act_date.isoformat(),
            "КонтрагентИд": str(act.company_id or ""), "СчетИд": f"inv-{act.invoice_id}" if act.invoice_id else "",
            "СтавкаНДС": str(act.vat_rate), "Сумма": f"{Decimal(act.amount):.2f}"})
        add_lines(el, act.items)
        act.exported_1c_at = utcnow()
    ET.indent(root)
    xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    audit(db, user, "export_1c", f"Выгрузка в 1С: {len(invoices)} счетов, {len(acts)} актов", entity="1c",
          request=request)
    db.commit()
    return Response(xml, media_type="application/xml",
                    headers={"Content-Disposition": f"attachment; filename=crm_1c_{date_from}_{date_to}.xml"})

