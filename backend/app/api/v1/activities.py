import hmac
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require
from app.core.config import settings
from app.core.permissions import has_perm
from app.core.security import phone_hash, random_token
from app.db.base import utcnow
from app.db.session import get_db
from app.models import Activity, AuditLog, Company, Contact, Deal, EmailMessage, FileAttachment, Lead, User
from app.schemas.activity import ActivityCreate, ActivityOut, AuditOut, CallIn, EmailOut, EmailSendIn, TelephonyEvent
from app.schemas.common import Page
from app.schemas.documents import FileOut
from app.services import access, telephony
from app.services.common import paginate
from app.services.journal import audit, log_activity
from app.services.leads import register_lead
from app.services.mailer import text_to_html, tracking_pixel
from app.services.notify import enqueue, notify
from app.services.storage import get_storage, make_key

router = APIRouter(tags=["Активности, почта, телефония, файлы"])

MAX_FILE_MB = 25


def _check_parent(db: Session, user: User, *, company_id=None, contact_id=None, deal_id=None, lead_id=None):
    if deal_id:
        if not has_perm(user.role, "deals.view"):
            raise HTTPException(403, "Недостаточно прав")
        access.get_deal(db, user, deal_id)
    if company_id:
        access.get_company(db, user, company_id)
    if contact_id:
        access.get_contact(db, user, contact_id)
    if lead_id:
        access.get_lead(db, user, lead_id)


# ---------- Лента активностей ----------

@router.get("/activities", response_model=Page[ActivityOut], summary="Хронологическая лента взаимодействий")
def timeline(
    company_id: int | None = None,
    contact_id: int | None = None,
    deal_id: int | None = None,
    lead_id: int | None = None,
    type: list[str] = Query(default=[]),
    page: int = 1,
    page_size: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_parent(db, user, company_id=company_id, contact_id=contact_id, deal_id=deal_id, lead_id=lead_id)
    stmt = select(Activity)
    if company_id:
        stmt = stmt.where(Activity.company_id == company_id)
    elif contact_id:
        stmt = stmt.where(Activity.contact_id == contact_id)
    elif deal_id:
        stmt = stmt.where(Activity.deal_id == deal_id)
    elif lead_id:
        stmt = stmt.where(Activity.lead_id == lead_id)
    elif not has_perm(user.role, "deals.view_all"):
        stmt = stmt.where(Activity.user_id == user.id)
    if type:
        stmt = stmt.where(Activity.type.in_(type))
    stmt = stmt.order_by(Activity.occurred_at.desc(), Activity.id.desc())
    return paginate(db, stmt, page, page_size, unique=True)


@router.post("/activities", response_model=ActivityOut, status_code=201, summary="Заметка / звонок / встреча")
def create_activity(data: ActivityCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _check_parent(db, user, company_id=data.company_id, contact_id=data.contact_id, deal_id=data.deal_id,
                  lead_id=data.lead_id)
    company_id = data.company_id
    if not company_id and data.contact_id:
        company_id = db.get(Contact, data.contact_id).company_id
    if not company_id and data.deal_id:
        company_id = db.get(Deal, data.deal_id).company_id
    obj_type, obj_id = next(((t, i) for t, i in (("deal", data.deal_id), ("contact", data.contact_id),
                                                 ("company", company_id), ("lead", data.lead_id)) if i), (None, None))
    if obj_type is None:
        raise HTTPException(422, "Укажите, к чему относится запись")
    default_titles = {"note": "Заметка", "call": "Звонок", "meeting": "Встреча"}
    meta = {}
    if data.duration_minutes:
        meta["duration_minutes"] = data.duration_minutes
    if data.direction:
        meta["direction"] = data.direction
    act = log_activity(db, type=data.type, title=data.title or default_titles[data.type], body=data.body,
                       object_type=obj_type, object_id=obj_id, user=user, company_id=company_id,
                       contact_id=data.contact_id, deal_id=data.deal_id, lead_id=data.lead_id, meta=meta,
                       occurred_at=data.occurred_at, touch_company=data.type != "note")
    if data.lead_id:
        lead = db.get(Lead, data.lead_id)
        if lead and lead.first_response_at is None:
            lead.first_response_at = utcnow()
            lead.status = "in_progress" if lead.status == "new" else lead.status
    db.commit()
    db.refresh(act)
    return act


@router.delete("/activities/{activity_id}")
def delete_activity(activity_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    act = db.get(Activity, activity_id)
    if act is None or act.type != "note" or (act.user_id != user.id and user.role not in ("admin", "head")):
        raise HTTPException(403, "Удалить можно только свою заметку")
    db.delete(act)
    db.commit()
    return {"detail": "Удалено"}


# ---------- Почта ----------

@router.post("/emails", response_model=EmailOut, status_code=201, summary="Отправить письмо из CRM (с трекингом)")
def send_email(data: EmailSendIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _check_parent(db, user, company_id=data.company_id, contact_id=data.contact_id, deal_id=data.deal_id,
                  lead_id=data.lead_id)
    company_id = data.company_id or (db.get(Contact, data.contact_id).company_id if data.contact_id else None)
    token = random_token(18)
    files = db.scalars(select(FileAttachment).where(FileAttachment.id.in_(data.file_ids))).all() if data.file_ids else []
    em = EmailMessage(direction="out", status="queued", subject=data.subject, body=data.body, from_email=user.email,
                      to_email=data.to, user_id=user.id, company_id=company_id, contact_id=data.contact_id,
                      deal_id=data.deal_id, lead_id=data.lead_id, tracking_token=token,
                      attachments=[{"id": f.id, "name": f.name} for f in files])
    db.add(em)
    db.flush()
    html = f"<div>{text_to_html(data.body)}</div>{tracking_pixel(token)}"
    obj_type, obj_id = next(((t, i) for t, i in (("deal", data.deal_id), ("contact", data.contact_id),
                                                 ("company", company_id), ("lead", data.lead_id)) if i),
                            ("email", em.id))
    log_activity(db, type="email_out", title=f"Письмо: {data.subject}", body=data.body, object_type=obj_type,
                 object_id=obj_id, user=user, company_id=company_id, contact_id=data.contact_id,
                 deal_id=data.deal_id, lead_id=data.lead_id, meta={"email_id": em.id, "to": data.to},
                 touch_company=True)
    if data.lead_id:
        lead = db.get(Lead, data.lead_id)
        if lead and lead.first_response_at is None:
            lead.first_response_at = utcnow()
            lead.status = "in_progress" if lead.status == "new" else lead.status
    db.commit()
    from app.worker.tasks import send_email_task

    enqueue(send_email_task, data.to, data.subject, html, data.body, em.id,
            [(f.name, f.storage_key, f.content_type) for f in files])
    return em


@router.get("/emails", response_model=list[EmailOut])
def list_emails(company_id: int | None = None, contact_id: int | None = None, deal_id: int | None = None,
                lead_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _check_parent(db, user, company_id=company_id, contact_id=contact_id, deal_id=deal_id, lead_id=lead_id)
    stmt = select(EmailMessage).order_by(EmailMessage.created_at.desc()).limit(100)
    conds = []
    for col, val in ((EmailMessage.company_id, company_id), (EmailMessage.contact_id, contact_id),
                     (EmailMessage.deal_id, deal_id), (EmailMessage.lead_id, lead_id)):
        if val:
            conds.append(col == val)
    if not conds:
        stmt = stmt.where(EmailMessage.user_id == user.id)
    else:
        stmt = stmt.where(or_(*conds))
    return db.scalars(stmt).all()


# ---------- Телефония ----------

@router.post("/telephony/call", summary="Click-to-call: АТС соединяет менеджера с клиентом")
def click_to_call(data: CallIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _check_parent(db, user, company_id=data.company_id, contact_id=data.contact_id, deal_id=data.deal_id,
                  lead_id=data.lead_id)
    try:
        result = telephony.click_to_call(user.sip_extension, data.phone)
    except telephony.TelephonyError as exc:
        raise HTTPException(502, str(exc))
    company_id = data.company_id or (db.get(Contact, data.contact_id).company_id if data.contact_id else None)
    obj_type, obj_id = next(((t, i) for t, i in (("deal", data.deal_id), ("contact", data.contact_id),
                                                 ("company", company_id), ("lead", data.lead_id)) if i),
                            ("user", user.id))
    log_activity(db, type="call", title=f"Исходящий звонок: {data.phone}", object_type=obj_type, object_id=obj_id,
                 user=user, company_id=company_id, contact_id=data.contact_id, deal_id=data.deal_id,
                 lead_id=data.lead_id, meta={"direction": "out", "phone": data.phone, **result},
                 touch_company=True)
    if data.lead_id:
        lead = db.get(Lead, data.lead_id)
        if lead and lead.first_response_at is None:
            lead.first_response_at = utcnow()
            lead.status = "in_progress" if lead.status == "new" else lead.status
    db.commit()
    return result


def _find_by_phone(db: Session, phone: str) -> tuple[Contact | None, Company | None]:
    h = phone_hash(phone)
    if not h:
        return None, None
    contact = db.scalars(select(Contact).where(Contact.deleted_at.is_(None), or_(
        Contact.phone_mobile_hash == h, Contact.phone_work_hash == h))).first()
    if contact:
        return contact, contact.company
    return None, db.scalars(select(Company).where(Company.phone_hash == h, Company.deleted_at.is_(None))).first()


@router.post("/integrations/telephony/events", summary="Вебхук АТС: входящие/исходящие звонки, запись разговора")
def telephony_event(event: TelephonyEvent, x_webhook_secret: str = Header(default=""), db: Session = Depends(get_db)):
    if not hmac.compare_digest(x_webhook_secret, settings.TELEPHONY_WEBHOOK_SECRET):
        raise HTTPException(403, "Неверный секрет вебхука")
    contact, company = _find_by_phone(db, event.phone)
    user = db.scalars(select(User).where(User.sip_extension == event.extension)).first() if event.extension else None
    if user is None and company:
        user = company.manager
    caller = contact.full_name if contact else (company.name if company else event.phone)

    if event.event == "incoming":
        # Определение номера: всплывающее уведомление менеджеру с карточкой клиента
        link = f"/contacts/{contact.id}" if contact else (f"/companies/{company.id}" if company else None)
        if user:
            notify(db, user.id, f"📞 Входящий звонок: {caller}",
                   f"{company.name if company else 'Новый номер'} · {event.phone}", link=link, kind="call",
                   email=False, telegram=False)
        db.commit()
        return {"contact_id": contact.id if contact else None, "company_id": company.id if company else None,
                "caller": caller}

    if event.event in ("completed", "missed"):
        title = ("Пропущенный" if event.event == "missed" else ("Входящий" if event.direction == "in" else "Исходящий")) \
            + f" звонок: {caller}"
        meta = {"direction": event.direction, "phone": event.phone, "call_id": event.call_id,
                "duration": event.duration, "recording_url": event.recording_url, "missed": event.event == "missed"}
        lead = None
        if contact is None and company is None and event.direction == "in":
            # Неизвестный номер — автоматически создаём лид с источником «Телефон»
            lead = register_lead(db, {"title": f"Звонок с номера {event.phone}", "phone": event.phone,
                                      "assigned_to": user.id if user else None}, source_code="phone")
        obj_type, obj_id = ("contact", contact.id) if contact else (("company", company.id) if company else
                                                                    ("lead", lead.id if lead else 0))
        log_activity(db, type="call", title=title, object_type=obj_type, object_id=obj_id, user=user,
                     company_id=company.id if company else None, contact_id=contact.id if contact else None,
                     lead_id=lead.id if lead else None, meta=meta, occurred_at=event.started_at,
                     touch_company=event.event == "completed")
        if event.event == "missed" and user:
            notify(db, user.id, f"Пропущенный звонок: {caller}", event.phone, kind="call", email=False)
        db.commit()
    return {"detail": "ok"}


# ---------- Файлы ----------

@router.get("/files", response_model=list[FileOut])
def list_files(deal_id: int | None = None, company_id: int | None = None, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if not deal_id and not company_id:
        raise HTTPException(422, "Укажите сделку или компанию")
    _check_parent(db, user, deal_id=deal_id, company_id=company_id)
    stmt = select(FileAttachment).order_by(FileAttachment.created_at.desc())
    if deal_id:
        stmt = stmt.where(FileAttachment.deal_id == deal_id)
    else:
        deal_ids = select(Deal.id).where(Deal.company_id == company_id)
        stmt = stmt.where(or_(FileAttachment.company_id == company_id, FileAttachment.deal_id.in_(deal_ids)))
    return db.scalars(stmt).all()


@router.post("/files", response_model=FileOut, status_code=201)
def upload_file(file: UploadFile = File(...), deal_id: int | None = Form(default=None),
                company_id: int | None = Form(default=None), doc_type: str = Form(default="other"),
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not deal_id and not company_id:
        raise HTTPException(422, "Укажите сделку или компанию")
    _check_parent(db, user, deal_id=deal_id, company_id=company_id)
    if doc_type not in ("proposal", "contract", "invoice", "act", "presentation", "other"):
        doc_type = "other"
    data = file.file.read(MAX_FILE_MB * 1024 * 1024 + 1)
    if len(data) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(413, f"Файл больше {MAX_FILE_MB} МБ")
    name = (file.filename or "file").replace("/", "_").replace("\\", "_")[:255]
    key = make_key("deals" if deal_id else "companies", name)
    get_storage().put(key, data, file.content_type)
    fa = FileAttachment(deal_id=deal_id, company_id=company_id, doc_type=doc_type, name=name, storage_key=key,
                        content_type=file.content_type, size=len(data), uploaded_by=user.id)
    db.add(fa)
    db.flush()
    log_activity(db, type="file", title=f"Загружен файл: {name}", object_type="deal" if deal_id else "company",
                 object_id=deal_id or company_id, user=user, deal_id=deal_id, company_id=company_id,
                 meta={"file_id": fa.id})
    db.commit()
    db.refresh(fa)
    return fa


def _get_file(db: Session, user: User, file_id: int) -> FileAttachment:
    fa = db.get(FileAttachment, file_id)
    if fa is None:
        raise HTTPException(404, "Файл не найден")
    _check_parent(db, user, deal_id=fa.deal_id, company_id=fa.company_id if not fa.deal_id else None)
    return fa


@router.get("/files/{file_id}/download")
def download_file(file_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from urllib.parse import quote

    fa = _get_file(db, user, file_id)
    return Response(get_storage().get(fa.storage_key), media_type=fa.content_type or "application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(fa.name)}"})


@router.delete("/files/{file_id}")
def delete_file(file_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fa = _get_file(db, user, file_id)
    if user.role == "manager" and fa.uploaded_by != user.id:
        raise HTTPException(403, "Удалить можно только загруженный вами файл")
    get_storage().delete(fa.storage_key)
    audit(db, user, "file_delete", f"Удалён файл «{fa.name}»", entity="file", entity_id=fa.id, request=request)
    db.delete(fa)
    db.commit()
    return {"detail": "Файл удалён"}


# ---------- Журнал аудита ----------

@router.get("/audit", response_model=Page[AuditOut], tags=["Администрирование"])
def audit_log(
    user_id: int | None = None,
    action: list[str] = Query(default=[]),
    entity: str | None = None,
    entity_id: int | None = None,
    days: int = 30,
    page: int = 1,
    page_size: int = 50,
    user: User = Depends(require("audit.view")),
    db: Session = Depends(get_db),
):
    stmt = select(AuditLog).where(AuditLog.created_at >= utcnow() - timedelta(days=days))
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action.in_(action))
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    return paginate(db, stmt.order_by(AuditLog.created_at.desc()), page, page_size, unique=True)
