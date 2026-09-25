from datetime import date, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require
from app.db.base import utcnow
from app.db.session import get_db
from app.models import Activity, ReportSchedule, Task, User
from app.schemas.activity import ActivityOut
from app.schemas.documents import ReportScheduleIn, ReportScheduleOut
from app.services import analytics
from app.services.documents import export_report
from app.services.journal import audit

router = APIRouter(prefix="/analytics", tags=["Аналитика и отчётность"])

REPORTS = {"summary": "Сводный отчёт", "funnel": "Воронка продаж", "managers": "Эффективность менеджеров",
           "sources": "Источники лидов", "products": "Продуктовая аналитика",
           "receivables": "Дебиторская задолженность"}


def _period(date_from: date | None, date_to: date | None) -> analytics.Period:
    if date_from and date_to:
        if date_from > date_to:
            raise HTTPException(422, "Дата начала позже даты окончания")
        return analytics.Period(date_from, date_to)
    return analytics.default_period("month")


@router.get("/dashboard", summary="Дашборд: KPI, выручка, воронка, прогноз, топ менеджеров, задачи")
def dashboard(date_from: date | None = None, date_to: date | None = None, owner_id: int | None = None,
              user: User = Depends(require("analytics.view")), db: Session = Depends(get_db)):
    period = _period(date_from, date_to)
    scope = analytics.make_scope(user, owner_id)
    # сравнение с предыдущим периодом такой же длины
    length = (period.date_to - period.date_from).days + 1
    prev = analytics.Period(period.date_from - timedelta(days=length), period.date_from - timedelta(days=1))
    summary = analytics.summary(db, period, scope)
    summary_prev = analytics.summary(db, prev, scope)

    now = utcnow()
    tq = select(Task).where(Task.status == "open", Task.due_at < now + timedelta(days=1))
    tq = tq.where(Task.assignee_id == (owner_id or user.id)) if (owner_id or user.role in ("manager", "marketer")) \
        else tq.where(Task.assignee_id == user.id)
    from app.api.v1.tasks import enrich

    tasks = enrich(db, list(db.scalars(tq.order_by(Task.due_at).limit(15)).unique()))

    aq = select(Activity).order_by(Activity.occurred_at.desc()).limit(12)
    if scope.owner_id:
        aq = aq.where(Activity.user_id == scope.owner_id)
    activities = [ActivityOut.model_validate(a).model_dump(mode="json") for a in db.scalars(aq).unique()]

    managers = analytics.managers(db, period, scope)["rows"][:5] if user.role != "manager" else []
    funnel = analytics.pipeline_by_stage(db, scope)
    return {
        "period": {"from": period.date_from, "to": period.date_to},
        "summary": summary,
        "previous": summary_prev,
        "revenue_by_month": analytics.revenue_by_month(db, scope, period),
        "forecast": analytics.forecast_by_month(db, scope),
        "funnel": funnel,
        "top_managers": managers,
        "tasks": [t.model_dump(mode="json") for t in tasks],
        "activities": activities,
    }


@router.get("/reports", summary="Список стандартных отчётов")
def reports_list(user: User = Depends(require("analytics.view"))):
    return [{"key": k, "title": v} for k, v in REPORTS.items()] + [
        {"key": "custom", "title": "Конструктор отчётов", "metrics": analytics.METRICS, "groups": analytics.GROUPS}]


def _build(db: Session, user: User, name: str, date_from, date_to, owner_id, source_id, industry_id, region_id,
           metric=None, group_by=None) -> dict:
    period = _period(date_from, date_to)
    scope = analytics.make_scope(user, owner_id, source_id=source_id, industry_id=industry_id, region_id=region_id)
    try:
        if name == "custom":
            return analytics.custom(db, period, scope, metric or "revenue", group_by or "month")
        if name == "receivables" and user.role == "marketer":
            raise HTTPException(403, "Недостаточно прав")
        return analytics.build_report(db, name, period, scope)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.get("/reports/{name}", summary="Данные отчёта (для таблицы и графиков)")
def report(name: str, date_from: date | None = None, date_to: date | None = None, owner_id: int | None = None,
           source_id: int | None = None, industry_id: int | None = None, region_id: int | None = None,
           metric: str | None = None, group_by: str | None = None,
           user: User = Depends(require("analytics.view")), db: Session = Depends(get_db)):
    return _build(db, user, name, date_from, date_to, owner_id, source_id, industry_id, region_id, metric, group_by)


@router.get("/reports/{name}/export", summary="Экспорт отчёта: PDF, Excel (.xlsx), CSV")
def report_export(name: str, request: Request, format: str = "xlsx", date_from: date | None = None,
                  date_to: date | None = None, owner_id: int | None = None, source_id: int | None = None,
                  industry_id: int | None = None, region_id: int | None = None, metric: str | None = None,
                  group_by: str | None = None, user: User = Depends(require("analytics.view")),
                  db: Session = Depends(get_db)):
    if format not in ("pdf", "xlsx", "csv"):
        raise HTTPException(422, "Формат: pdf, xlsx или csv")
    data = _build(db, user, name, date_from, date_to, owner_id, source_id, industry_id, region_id, metric, group_by)
    content, mime, ext = export_report(db, data, format)
    audit(db, user, "export", f"Экспорт отчёта «{data['title']}» в {ext.upper()}", entity="report", request=request)
    db.commit()
    filename = f"{data['title']}.{ext}"
    return Response(content, media_type=mime,
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})


# ---------- Рассылка отчётов по расписанию ----------

@router.get("/schedules", response_model=list[ReportScheduleOut])
def schedules(user: User = Depends(require("analytics.view")), db: Session = Depends(get_db)):
    return db.scalars(select(ReportSchedule).where(ReportSchedule.user_id == user.id)
                      .order_by(ReportSchedule.id)).all()


@router.post("/schedules", response_model=ReportScheduleOut, status_code=201)
def create_schedule(data: ReportScheduleIn, user: User = Depends(require("analytics.view")),
                    db: Session = Depends(get_db)):
    s = ReportSchedule(user_id=user.id, **data.model_dump())
    db.add(s)
    db.commit()
    return s


@router.patch("/schedules/{schedule_id}", response_model=ReportScheduleOut)
def update_schedule(schedule_id: int, data: ReportScheduleIn, user: User = Depends(require("analytics.view")),
                    db: Session = Depends(get_db)):
    s = db.get(ReportSchedule, schedule_id)
    if s is None or s.user_id != user.id:
        raise HTTPException(404, "Расписание не найдено")
    for k, v in data.model_dump().items():
        setattr(s, k, v)
    db.commit()
    return s


@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, user: User = Depends(require("analytics.view")), db: Session = Depends(get_db)):
    s = db.get(ReportSchedule, schedule_id)
    if s is None or s.user_id != user.id:
        raise HTTPException(404, "Расписание не найдено")
    db.delete(s)
    db.commit()
    return {"detail": "Удалено"}


@router.post("/schedules/{schedule_id}/send-now", summary="Отправить отчёт сейчас (проверка)")
def send_now(schedule_id: int, user: User = Depends(require("analytics.view")), db: Session = Depends(get_db)):
    s = db.get(ReportSchedule, schedule_id)
    if s is None or s.user_id != user.id:
        raise HTTPException(404, "Расписание не найдено")
    period = analytics.default_period("week" if s.frequency == "weekly" else "prev_month")
    data = analytics.build_report(db, s.report, period, analytics.make_scope(user))
    content, mime, ext = export_report(db, data, s.format)
    from app.services.notify import enqueue
    from app.services.storage import get_storage, make_key
    from app.worker.tasks import send_email_task

    key = make_key("reports", f"report.{ext}")
    get_storage().put(key, content, mime)
    enqueue(send_email_task, s.email, f"Отчёт: {data['title']} ({period.label})",
            f"<p>Отчёт «{data['title']}» за период {period.label} во вложении.</p>", None, None,
            [(f"{s.report}.{ext}", key, mime)])
    s.last_sent_at = utcnow()
    db.commit()
    return {"detail": f"Отчёт отправлен на {s.email}"}
