from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require
from app.core.config import settings
from app.core.security import random_token
from app.db.base import utcnow
from app.db.session import get_db
from app.models import Company, Contact, FileAttachment, Product, Proposal, ProposalItem, ProposalTemplate, User
from app.schemas.common import Page
from app.schemas.documents import (
    LineIn,
    ProposalCreate,
    ProposalDetail,
    ProposalOut,
    ProposalSend,
    ProposalUpdate,
    TemplateIn,
    TemplateOut,
)
from app.services import access
from app.services.common import next_number, paginate
from app.services.documents import VARIABLES, proposal_pdf
from app.services.journal import audit, log_activity
from app.services.mailer import text_to_html, tracking_pixel
from app.services.notify import enqueue
from app.services.storage import get_storage, make_key

router = APIRouter(tags=["Коммерческие предложения"])

STATUS_LABELS = {"draft": "Черновик", "sent": "Отправлено", "viewed": "Просмотрено", "approved": "Согласовано",
                 "rejected": "Отклонено"}


def public_url(p: Proposal) -> str:
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/p/{p.tracking_token}"


def _out(p: Proposal, detail: bool = True):
    model = ProposalDetail if detail else ProposalOut
    out = model.model_validate(p)
    out.public_url = public_url(p)
    return out


# ---------- Шаблоны ----------

@router.get("/proposal-templates", response_model=list[TemplateOut])
def templates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(ProposalTemplate).order_by(ProposalTemplate.name)).all()


@router.get("/proposal-templates/variables", summary="Переменные для подстановки в шаблоны")
def variables(user: User = Depends(get_current_user)):
    return [{"key": k, "label": v} for k, v in VARIABLES.items()]


@router.post("/proposal-templates", response_model=TemplateOut, status_code=201)
def create_template(data: TemplateIn, user: User = Depends(require("templates.edit")), db: Session = Depends(get_db)):
    t = ProposalTemplate(**data.model_dump())
    db.add(t)
    db.commit()
    return t


@router.patch("/proposal-templates/{template_id}", response_model=TemplateOut)
def update_template(template_id: int, data: TemplateIn, user: User = Depends(require("templates.edit")),
                    db: Session = Depends(get_db)):
    t = db.get(ProposalTemplate, template_id)
    if t is None:
        raise HTTPException(404, "Шаблон не найден")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    db.commit()
    return t


@router.delete("/proposal-templates/{template_id}")
def delete_template(template_id: int, user: User = Depends(require("templates.edit")), db: Session = Depends(get_db)):
    t = db.get(ProposalTemplate, template_id)
    if t is None:
        raise HTTPException(404, "Шаблон не найден")
    t.is_active = False
    db.commit()
    return {"detail": "Шаблон отключён"}


# ---------- КП ----------

def _set_items(p: Proposal, items: list[LineIn]) -> None:
    p.items.clear()
    total = Decimal(0)
    for idx, it in enumerate(items):
        item = ProposalItem(product_id=it.product_id, name=it.name, description=it.description,
                            quantity=it.quantity, unit=it.unit, price=it.price,
                            discount_percent=it.discount_percent, sort=idx)
        p.items.append(item)
        total += item.total
    p.total = total


@router.get("/proposals", response_model=Page[ProposalOut])
def list_proposals(
    q: str | None = None,
    status: list[str] = Query(default=[]),
    deal_id: int | None = None,
    company_id: int | None = None,
    page: int = 1,
    page_size: int = 25,
    user: User = Depends(require("proposals.edit")),
    db: Session = Depends(get_db),
):
    stmt = access.scope_proposals(select(Proposal), user)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Proposal.title).like(like), func.lower(Proposal.number).like(like),
                              Proposal.company_id.in_(select(Company.id).where(func.lower(Company.name).like(like)))))
    if status:
        stmt = stmt.where(Proposal.status.in_(status))
    if deal_id:
        stmt = stmt.where(Proposal.deal_id == deal_id)
    if company_id:
        stmt = stmt.where(Proposal.company_id == company_id)
    res = paginate(db, stmt.order_by(Proposal.created_at.desc()), page, page_size, unique=True)
    res["items"] = [_out(p, detail=False) for p in res["items"]]
    return res


@router.post("/proposals", response_model=ProposalDetail, status_code=201,
             summary="Создать КП (из сделки, шаблона и каталога)")
def create_proposal(data: ProposalCreate, user: User = Depends(require("proposals.edit")),
                    db: Session = Depends(get_db)):
    deal = access.get_deal(db, user, data.deal_id) if data.deal_id else None
    company_id = data.company_id or (deal.company_id if deal else None)
    company = access.get_company(db, user, company_id) if company_id else None
    contact_id = data.contact_id or (deal.contact_id if deal else None)
    contact = db.get(Contact, contact_id) if contact_id else None
    template = db.get(ProposalTemplate, data.template_id) if data.template_id else None
    items = data.items
    if items is None and deal and deal.products:
        items = [LineIn(product_id=dp.product_id, name=dp.name, quantity=float(dp.quantity), unit=dp.unit,
                        price=float(dp.price), discount_percent=float(dp.discount_percent)) for dp in deal.products]
    if items is None and deal and not deal.products and float(deal.amount or 0) > 0:
        items = [LineIn(name=deal.title, quantity=1, unit="усл.", price=float(deal.amount))]
    if items is None and template and template.default_items:
        items = []
        for di in template.default_items:
            prod = db.get(Product, di.get("product_id"))
            if prod:
                items.append(LineIn(product_id=prod.id, name=prod.name, description=prod.description,
                                    quantity=di.get("quantity", 1), unit=prod.unit, price=float(prod.price)))
    valid_until = data.valid_until or date.today() + timedelta(days=14)
    intro = data.intro_text if data.intro_text is not None else (template.intro_text if template else "")
    terms = data.terms_text if data.terms_text is not None else (template.terms_text if template else "")
    p = Proposal(
        number=next_number(db, "КП"),
        title=data.title or (f"Коммерческое предложение для {company.name}" if company else "Коммерческое предложение"),
        deal_id=deal.id if deal else None, company_id=company.id if company else None,
        contact_id=contact.id if contact else None, template_id=template.id if template else None, owner_id=user.id,
        currency=data.currency or (deal.currency if deal else "RUB"), vat_rate=data.vat_rate, valid_until=valid_until,
        # Переменные ({{клиент.название}} и т.п.) подставляются при формировании PDF и публичной страницы,
        # чтобы сумма и реквизиты всегда были актуальными
        intro_text=intro,
        terms_text=terms,
        tracking_token=random_token(18),
    )
    db.add(p)
    db.flush()
    _set_items(p, items or [])
    if deal:
        log_activity(db, type="proposal", title=f"Подготовлено КП {p.number}", object_type="deal", object_id=deal.id,
                     user=user, deal_id=deal.id, company_id=p.company_id, meta={"proposal_id": p.id})
    db.commit()
    db.refresh(p)
    return _out(p)


@router.get("/proposals/{proposal_id}", response_model=ProposalDetail)
def get_proposal(proposal_id: int, user: User = Depends(require("proposals.edit")), db: Session = Depends(get_db)):
    return _out(access.get_proposal(db, user, proposal_id))


@router.patch("/proposals/{proposal_id}", response_model=ProposalDetail)
def update_proposal(proposal_id: int, data: ProposalUpdate, user: User = Depends(require("proposals.edit")),
                    db: Session = Depends(get_db)):
    p = access.get_proposal(db, user, proposal_id)
    values = data.model_dump(exclude_unset=True, exclude={"items"})
    new_status = values.pop("status", None)
    if p.status in ("approved", "rejected") and values:
        raise HTTPException(400, "Согласованное или отклонённое КП нельзя изменить — создайте новую версию")
    for k, v in values.items():
        setattr(p, k, v)
    if data.items is not None:
        _set_items(p, data.items)
    if new_status and new_status != p.status:
        p.status = new_status
        if new_status in ("approved", "rejected"):
            p.decided_at = utcnow()
        log_activity(db, type="proposal", title=f"КП {p.number}: {STATUS_LABELS[new_status]}", object_type="deal"
                     if p.deal_id else "company", object_id=p.deal_id or p.company_id or 0, user=user,
                     deal_id=p.deal_id, company_id=p.company_id, meta={"proposal_id": p.id})
    db.commit()
    db.refresh(p)
    return _out(p)


@router.post("/proposals/{proposal_id}/duplicate", response_model=ProposalDetail, summary="Новая версия КП")
def duplicate_proposal(proposal_id: int, user: User = Depends(require("proposals.edit")),
                       db: Session = Depends(get_db)):
    src = access.get_proposal(db, user, proposal_id)
    p = Proposal(number=next_number(db, "КП"), title=src.title, deal_id=src.deal_id, company_id=src.company_id,
                 contact_id=src.contact_id, template_id=src.template_id, owner_id=user.id, currency=src.currency,
                 vat_rate=src.vat_rate, valid_until=date.today() + timedelta(days=14), intro_text=src.intro_text,
                 terms_text=src.terms_text, tracking_token=random_token(18))
    db.add(p)
    db.flush()
    _set_items(p, [LineIn(product_id=i.product_id, name=i.name, description=i.description, quantity=float(i.quantity),
                          unit=i.unit, price=float(i.price), discount_percent=float(i.discount_percent))
                   for i in src.items])
    db.commit()
    db.refresh(p)
    return _out(p)


@router.get("/proposals/{proposal_id}/pdf", summary="PDF с логотипом и фирменным стилем")
def proposal_pdf_view(proposal_id: int, download: bool = False, user: User = Depends(require("proposals.edit")),
                      db: Session = Depends(get_db)):
    p = access.get_proposal(db, user, proposal_id)
    pdf = proposal_pdf(db, p)
    disp = "attachment" if download else "inline"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"{disp}; filename*=UTF-8''{quote(p.number)}.pdf"})


@router.post("/proposals/{proposal_id}/send", response_model=ProposalDetail,
             summary="Отправить КП по email с отслеживанием открытия")
def send_proposal(proposal_id: int, data: ProposalSend, request: Request,
                  user: User = Depends(require("proposals.edit")), db: Session = Depends(get_db)):
    p = access.get_proposal(db, user, proposal_id)
    if not p.items:
        raise HTTPException(422, "Добавьте в КП хотя бы одну позицию")
    pdf = proposal_pdf(db, p)
    key = make_key("proposals", f"{p.number}.pdf")
    get_storage().put(key, pdf, "application/pdf")
    if p.deal_id:
        db.add(FileAttachment(deal_id=p.deal_id, company_id=p.company_id, doc_type="proposal",
                              name=f"{p.number}.pdf", storage_key=key, content_type="application/pdf",
                              size=len(pdf), uploaded_by=user.id))
    message = data.message or (
        f"Добрый день{', ' + p.contact.first_name if p.contact else ''}!\n\n"
        f"Направляю коммерческое предложение {p.number}. Его также можно посмотреть онлайн и сразу согласовать "
        f"по ссылке ниже.\n\nС уважением,\n{user.full_name}\n{user.position or ''}\n{user.phone or ''}")
    link = public_url(p)
    html = (f"<div>{text_to_html(message)}</div>"
            f"<p><a href='{link}' style='display:inline-block;padding:10px 18px;background:#1c7ed6;color:#fff;"
            f"border-radius:6px;text-decoration:none'>Открыть коммерческое предложение</a></p>"
            f"{tracking_pixel(p.tracking_token)}")
    from app.worker.tasks import send_email_task

    enqueue(send_email_task, data.to, data.subject or f"Коммерческое предложение {p.number}", html, message, None,
            [(f"{p.number}.pdf", key, "application/pdf")])
    p.status = "sent" if p.status == "draft" else p.status
    p.sent_at = utcnow()
    p.sent_to = data.to
    log_activity(db, type="proposal", title=f"КП {p.number} отправлено на {data.to}", body=message,
                 object_type="deal" if p.deal_id else "company", object_id=p.deal_id or p.company_id or 0,
                 user=user, deal_id=p.deal_id, company_id=p.company_id, contact_id=p.contact_id,
                 meta={"proposal_id": p.id}, touch_company=True)
    audit(db, user, "proposal_send", f"КП {p.number} отправлено на {data.to}", entity="proposal", entity_id=p.id,
          request=request)
    db.commit()
    db.refresh(p)
    return _out(p)


@router.delete("/proposals/{proposal_id}")
def delete_proposal(proposal_id: int, user: User = Depends(require("proposals.edit")), db: Session = Depends(get_db)):
    p = access.get_proposal(db, user, proposal_id)
    if p.status != "draft":
        raise HTTPException(400, "Удалить можно только черновик")
    db.delete(p)
    db.commit()
    return {"detail": "КП удалено"}

