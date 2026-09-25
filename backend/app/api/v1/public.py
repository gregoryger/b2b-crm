"""Публичные эндпоинты: приём лидов с сайта, трекинг-пиксель, онлайн-просмотр и согласование КП."""
import base64
import hashlib
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.session import get_db
from app.models import ApiKey, EmailMessage, Proposal
from app.schemas.crm import PublicLeadIn
from app.schemas.documents import PublicDecision
from app.services.common import get_setting
from app.services.documents import fill_variables, proposal_pdf
from app.services.journal import log_activity
from app.services.leads import register_lead
from app.services.money import calc_lines
from app.services.notify import notify

router = APIRouter(tags=["Публичный API"])

PIXEL = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")


def _api_key(db: Session, key: str) -> ApiKey:
    row = db.scalars(select(ApiKey).where(ApiKey.prefix == key[:12], ApiKey.is_active.is_(True))).first()
    if row is None or row.key_hash != hashlib.sha256(key.encode()).hexdigest():
        raise HTTPException(401, "Неверный API-ключ")
    return row


@router.post("/public/leads", status_code=201,
             summary="Приём заявок с веб-форм сайта (заголовок X-Api-Key)")
def public_lead(data: PublicLeadIn, x_api_key: str = Header(...), db: Session = Depends(get_db)):
    key = _api_key(db, x_api_key)
    key.last_used_at = utcnow()
    if not (data.phone or data.email):
        raise HTTPException(422, "Укажите телефон или email")
    title = f"Заявка с сайта: {data.company or data.name or data.email or data.phone}"
    lead = register_lead(db, {
        "title": title[:255], "contact_name": data.name, "company_name": data.company, "phone": data.phone,
        "email": data.email, "message": data.message, "inn": data.inn, "utm_source": data.utm_source,
        "utm_medium": data.utm_medium, "utm_campaign": data.utm_campaign,
    }, source_code=data.source or ("api" if key.name.lower().startswith("api") else "website"))
    db.commit()
    return {"id": lead.id, "detail": "Заявка принята"}


def _mark_proposal_viewed(db: Session, p: Proposal) -> None:
    first = p.viewed_at is None
    if first:
        p.viewed_at = utcnow()
    if p.status == "sent":
        p.status = "viewed"
    if first:
        log_activity(db, type="proposal", title=f"Клиент открыл КП {p.number}", object_type="deal" if p.deal_id
                     else "company", object_id=p.deal_id or p.company_id or 0, deal_id=p.deal_id,
                     company_id=p.company_id, meta={"proposal_id": p.id})
        notify(db, p.owner_id, f"Клиент открыл КП {p.number}", p.company.name if p.company else None,
               link=f"/proposals/{p.id}", kind="proposal", email=False)


@router.get("/t/{token}.gif", include_in_schema=False)
def tracking_pixel(token: str, db: Session = Depends(get_db)):
    em = db.scalars(select(EmailMessage).where(EmailMessage.tracking_token == token)).first()
    if em:
        em.open_count += 1
        if em.opened_at is None:
            em.opened_at = utcnow()
            if em.user_id:
                notify(db, em.user_id, "Письмо прочитано", f"{em.to_email}: {em.subject}", kind="email",
                       email=False, telegram=False)
        db.commit()
    else:
        p = db.scalars(select(Proposal).where(Proposal.tracking_token == token)).first()
        if p:
            _mark_proposal_viewed(db, p)
            db.commit()
    return Response(PIXEL, media_type="image/gif",
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"})


def _get_public(db: Session, token: str) -> Proposal:
    p = db.scalars(select(Proposal).where(Proposal.tracking_token == token)).first()
    if p is None or p.status == "draft":
        raise HTTPException(404, "Предложение не найдено")
    return p


@router.get("/public/proposals/{token}", summary="Онлайн-версия КП для клиента")
def public_proposal(token: str, db: Session = Depends(get_db)):
    p = _get_public(db, token)
    _mark_proposal_viewed(db, p)
    db.commit()
    profile = get_setting(db, "company_profile")
    items = [{"name": i.name, "description": i.description, "quantity": float(i.quantity), "unit": i.unit,
              "price": float(i.price), "discount_percent": float(i.discount_percent)} for i in p.items]
    calc = calc_lines(items, p.vat_rate)
    return {
        "number": p.number, "title": p.title, "status": p.status, "currency": p.currency, "vat_rate": p.vat_rate,
        "valid_until": p.valid_until, "created_at": p.created_at,
        "intro": fill_variables(p.intro_text, proposal=p, profile=profile),
        "terms": fill_variables(p.terms_text, proposal=p, profile=profile),
        "items": calc["lines"], "total": float(calc["total"]), "vat": float(calc["vat"]),
        "company": {"name": p.company.name} if p.company else None,
        "seller": {"name": profile.get("name"), "phone": profile.get("phone"), "email": profile.get("email"),
                   "website": profile.get("website"), "has_logo": bool(profile.get("logo_key")),
                   "accent_color": (p.template.accent_color if p.template else None) or profile.get("accent_color")},
        "manager": {"name": p.owner.full_name, "phone": p.owner.phone, "email": p.owner.email,
                    "position": p.owner.position} if p.owner else None,
        "client_comment": p.client_comment, "decided_at": p.decided_at,
    }


@router.get("/public/proposals/{token}/pdf", include_in_schema=False)
def public_proposal_pdf(token: str, db: Session = Depends(get_db)):
    p = _get_public(db, token)
    return Response(proposal_pdf(db, p), media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(p.number)}.pdf"})


@router.post("/public/proposals/{token}/decision", summary="Клиент согласует или отклоняет КП")
def public_decision(token: str, data: PublicDecision, request: Request, db: Session = Depends(get_db)):
    p = _get_public(db, token)
    if p.status in ("approved", "rejected"):
        raise HTTPException(400, "Решение по предложению уже принято")
    p.status = data.decision
    p.decided_at = utcnow()
    p.client_comment = data.comment
    label = "согласовал" if data.decision == "approved" else "отклонил"
    log_activity(db, type="proposal", title=f"Клиент {label} КП {p.number}", body=data.comment,
                 object_type="deal" if p.deal_id else "company", object_id=p.deal_id or p.company_id or 0,
                 deal_id=p.deal_id, company_id=p.company_id, meta={"proposal_id": p.id, "ip": request.client.host
                                                                   if request.client else None},
                 touch_company=True)
    notify(db, p.owner_id, f"{'✅' if data.decision == 'approved' else '❌'} Клиент {label} КП {p.number}",
           (p.company.name if p.company else "") + (f": {data.comment}" if data.comment else ""),
           link=f"/proposals/{p.id}", kind="proposal")
    db.commit()
    return {"status": p.status}


@router.get("/public/logo", include_in_schema=False)
def public_logo(db: Session = Depends(get_db)):
    from app.api.v1.reference import get_logo

    return get_logo(db)
