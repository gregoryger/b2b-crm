import hashlib
import hmac
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require
from app.core.config import settings
from app.core.permissions import has_perm
from app.db.base import utcnow
from app.db.session import get_db
from app.models import Company, Contact, Deal, Lead, Task, User
from app.schemas.activity import RelatedRef, TaskComplete, TaskCreate, TaskOut, TaskUpdate
from app.schemas.common import Page
from app.services import access
from app.services.common import paginate
from app.services.journal import audit, log_activity
from app.services.notify import notify

router = APIRouter(prefix="/tasks", tags=["Задачи и календарь"])

TYPE_LABELS = {"call": "Звонок", "meeting": "Встреча", "email": "Письмо", "proposal": "Подготовка КП",
               "other": "Задача"}


def enrich(db: Session, tasks: list[Task]) -> list[TaskOut]:
    """Добавляет названия связанных объектов (сделка, компания, контакт, лид)."""
    ids = {"deal": set(), "company": set(), "contact": set(), "lead": set()}
    for t in tasks:
        for kind in ids:
            if (v := getattr(t, f"{kind}_id")):
                ids[kind].add(v)
    names: dict[str, dict[int, str]] = {k: {} for k in ids}
    if ids["deal"]:
        names["deal"] = dict(db.execute(select(Deal.id, Deal.title).where(Deal.id.in_(ids["deal"]))).all())
    if ids["company"]:
        names["company"] = dict(db.execute(select(Company.id, Company.name).where(Company.id.in_(ids["company"]))).all())
    if ids["contact"]:
        names["contact"] = dict(db.execute(select(Contact.id, Contact.full_name)
                                           .where(Contact.id.in_(ids["contact"]))).all())
    if ids["lead"]:
        names["lead"] = dict(db.execute(select(Lead.id, Lead.title).where(Lead.id.in_(ids["lead"]))).all())
    now = utcnow()
    result = []
    for t in tasks:
        out = TaskOut.model_validate(t)
        out.related = [RelatedRef(type=k, id=getattr(t, f"{k}_id"), name=names[k].get(getattr(t, f"{k}_id"), "—"))
                       for k in ("deal", "company", "contact", "lead") if getattr(t, f"{k}_id")]
        out.is_overdue = t.status == "open" and t.due_at < now
        result.append(out)
    return result


def _day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


@router.get("", response_model=Page[TaskOut])
def list_tasks(
    scope: str = Query(default="mine", description="mine | created | all"),
    status: list[str] = Query(default=[]),
    type: list[str] = Query(default=[]),
    assignee_id: int | None = None,
    deal_id: int | None = None,
    company_id: int | None = None,
    contact_id: int | None = None,
    lead_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    overdue: bool = False,
    today: bool = False,
    page: int = 1,
    page_size: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = access.scope_tasks(select(Task), user)
    if scope == "mine":
        stmt = stmt.where(Task.assignee_id == user.id)
    elif scope == "created":
        stmt = stmt.where(Task.author_id == user.id)
    if assignee_id and has_perm(user.role, "tasks.view_all"):
        stmt = stmt.where(Task.assignee_id == assignee_id)
    if status:
        stmt = stmt.where(Task.status.in_(status))
    if type:
        stmt = stmt.where(Task.type.in_(type))
    for col, val in ((Task.deal_id, deal_id), (Task.company_id, company_id), (Task.contact_id, contact_id),
                     (Task.lead_id, lead_id)):
        if val:
            stmt = stmt.where(col == val)
    if date_from:
        stmt = stmt.where(Task.due_at >= date_from)
    if date_to:
        stmt = stmt.where(Task.due_at < date_to)
    if overdue:
        stmt = stmt.where(Task.status == "open", Task.due_at < utcnow())
    if today:
        start, end = _day_bounds(datetime.now(timezone(timedelta(hours=3))).date())  # «сегодня» по Москве
        stmt = stmt.where(Task.due_at >= start - timedelta(hours=3), Task.due_at < end - timedelta(hours=3))
    stmt = stmt.order_by(Task.status.desc(), Task.due_at.asc(), Task.id)
    page_data = paginate(db, stmt, page, min(page_size, 500), unique=True)
    page_data["items"] = enrich(db, page_data["items"])
    return page_data


def _validate_links(db: Session, user: User, data) -> dict:
    """Проверяет доступ к связанным объектам и подставляет компанию из сделки/контакта."""
    values = {}
    if getattr(data, "deal_id", None):
        deal = access.get_deal(db, user, data.deal_id) if has_perm(user.role, "deals.view") else None
        if deal is None:
            raise HTTPException(404, "Сделка не найдена")
        values["company_id"] = data.company_id or deal.company_id
    if getattr(data, "contact_id", None):
        contact = access.get_contact(db, user, data.contact_id)
        values["company_id"] = values.get("company_id") or data.company_id or contact.company_id
    if getattr(data, "company_id", None):
        access.get_company(db, user, data.company_id)
    if getattr(data, "lead_id", None):
        access.get_lead(db, user, data.lead_id)
    return values


@router.post("", response_model=TaskOut, status_code=201)
def create_task(data: TaskCreate, user: User = Depends(require("tasks.edit")), db: Session = Depends(get_db)):
    extra = _validate_links(db, user, data)
    values = data.model_dump()
    values.update(extra)
    assignee_id = values.get("assignee_id") or user.id
    if assignee_id != user.id and user.role == "manager":
        target = db.get(User, assignee_id)
        if target is None or not target.is_active:
            raise HTTPException(404, "Исполнитель не найден")
    values["assignee_id"] = assignee_id
    task = Task(author_id=user.id, **values)
    db.add(task)
    db.flush()
    if task.lead_id:
        lead = db.get(Lead, task.lead_id)
        if lead and lead.first_response_at is None:
            lead.first_response_at = utcnow()
            if lead.status == "new":
                lead.status = "in_progress"
    if assignee_id != user.id:
        local = task.due_at.astimezone(timezone(timedelta(hours=3)))
        notify(db, assignee_id, f"Новая задача: {TYPE_LABELS.get(task.type)}",
               f"{task.title} — срок {local:%d.%m %H:%M}", link=f"/tasks?open={task.id}", kind="task")
    db.commit()
    db.refresh(task)
    return enrich(db, [task])[0]


@router.get("/ics-url", summary="Ссылка на календарь для подписки в Google Calendar / Outlook")
def ics_url(user: User = Depends(get_current_user)):
    token = _ics_token(user.id)
    return {"url": f"{settings.PUBLIC_BASE_URL.rstrip('/')}/api/v1/tasks/ics/{user.id}/{token}.ics"}


def _ics_token(user_id: int) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), f"ics:{user_id}".encode(), hashlib.sha256).hexdigest()[:32]


def _ics_escape(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


@router.get("/ics/{user_id}/{token}.ics", include_in_schema=False)
def ics_feed(user_id: int, token: str, db: Session = Depends(get_db)):
    if not hmac.compare_digest(token, _ics_token(user_id)):
        raise HTTPException(404)
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(404)
    tasks = db.scalars(select(Task).where(Task.assignee_id == user_id, Task.status != "canceled",
                                          Task.due_at >= utcnow() - timedelta(days=60))).unique().all()
    fmt = "%Y%m%dT%H%M%SZ"
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//B2B CRM//RU", "CALSCALE:GREGORIAN",
             f"X-WR-CALNAME:{_ics_escape('CRM — ' + user.full_name)}"]
    for t in tasks:
        start = t.due_at.astimezone(timezone.utc)
        end = start + timedelta(minutes=t.duration_minutes or 30)
        lines += ["BEGIN:VEVENT", f"UID:crm-task-{t.id}@crm", f"DTSTAMP:{utcnow():{fmt}}",
                  f"DTSTART:{start:{fmt}}", f"DTEND:{end:{fmt}}",
                  f"SUMMARY:{_ics_escape(('✔ ' if t.status == 'done' else '') + TYPE_LABELS.get(t.type, '') + ': ' + t.title)}",
                  f"DESCRIPTION:{_ics_escape(t.description or '')}",
                  f"URL:{settings.PUBLIC_BASE_URL.rstrip('/')}/tasks?open={t.id}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return Response("\r\n".join(lines), media_type="text/calendar; charset=utf-8")


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return enrich(db, [access.get_task(db, user, task_id)])[0]


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(task_id: int, data: TaskUpdate, user: User = Depends(require("tasks.edit")),
                db: Session = Depends(get_db)):
    task = access.get_task(db, user, task_id)
    extra = _validate_links(db, user, data)
    values = data.model_dump(exclude_unset=True)
    values.update({k: v for k, v in extra.items() if k not in values})
    if "due_at" in values or "reminder_minutes" in values:
        task.reminder_sent_at = None
    old_assignee = task.assignee_id
    for k, v in values.items():
        setattr(task, k, v)
    if values.get("status") == "done" and task.completed_at is None:
        task.completed_at = utcnow()
    elif values.get("status") == "open":
        task.completed_at = None
    if task.assignee_id and task.assignee_id != old_assignee and task.assignee_id != user.id:
        notify(db, task.assignee_id, "Вам назначена задача", task.title, link=f"/tasks?open={task.id}", kind="task")
    db.commit()
    db.refresh(task)
    return enrich(db, [task])[0]


@router.post("/{task_id}/complete", response_model=TaskOut, summary="Завершить задачу с результатом")
def complete_task(task_id: int, data: TaskComplete, user: User = Depends(require("tasks.edit")),
                  db: Session = Depends(get_db)):
    task = access.get_task(db, user, task_id)
    task.status = "done"
    task.completed_at = utcnow()
    task.result = data.result
    act_type = {"call": "call", "meeting": "meeting"}.get(task.type, "task_done")
    log_activity(db, type=act_type, title=f"{TYPE_LABELS.get(task.type)}: {task.title}", body=data.result,
                 object_type="task", object_id=task.id, user=user, deal_id=task.deal_id, company_id=task.company_id,
                 contact_id=task.contact_id, lead_id=task.lead_id, meta={"task_id": task.id, "completed": True},
                 touch_company=True)
    if task.author_id and task.author_id != user.id:
        notify(db, task.author_id, "Задача выполнена", f"{task.title}. {data.result or ''}".strip(),
               link=f"/tasks?open={task.id}", kind="task", email=False)
    db.commit()
    db.refresh(task)
    return enrich(db, [task])[0]


@router.delete("/{task_id}")
def delete_task(task_id: int, request: Request, user: User = Depends(require("tasks.edit")),
                db: Session = Depends(get_db)):
    task = access.get_task(db, user, task_id)
    if user.role == "manager" and task.author_id != user.id:
        raise HTTPException(403, "Удалить задачу может только её автор")
    audit(db, user, "delete", f"Удалена задача «{task.title}»", entity="task", entity_id=task.id, request=request)
    db.delete(task)
    db.commit()
    return {"detail": "Задача удалена"}
