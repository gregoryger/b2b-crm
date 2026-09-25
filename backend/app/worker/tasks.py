"""Фоновые задачи: письма, Telegram, напоминания, отчёты по расписанию, разбор почты."""
import logging
from datetime import date, timedelta

from sqlalchemy import func, select

from app.core.security import random_token
from app.db.base import utcnow
from app.db.session import SessionLocal
from app.models import Contact, EmailMessage, Lead, ReportSchedule, SystemSetting, Task, User
from app.services import mailer, telegram
from app.worker.celery_app import celery

log = logging.getLogger(__name__)

TASK_TYPES = {"call": "Звонок", "meeting": "Встреча", "email": "Письмо", "proposal": "Подготовка КП",
              "other": "Задача"}


@celery.task(bind=True, max_retries=3, name="app.worker.tasks.send_email_task")
def send_email_task(self, to: str, subject: str, html: str, text: str | None = None,
                    email_id: int | None = None, attachments: list | None = None):
    """attachments: [(имя, storage_key, mime)] — файлы читаются из хранилища."""
    files = []
    if attachments:
        from app.services.storage import get_storage

        storage = get_storage()
        files = [(name, storage.get(key), mime) for name, key, mime in attachments]
    try:
        msg_id = mailer.send_email(to, subject, html, text=text, attachments=files)
    except Exception as exc:
        log.warning("Ошибка отправки письма на %s: %s", to, exc)
        if email_id:
            with SessionLocal() as db:
                em = db.get(EmailMessage, email_id)
                if em:
                    em.status, em.error = "failed", str(exc)[:1000]
                    db.commit()
        if not celery.conf.task_always_eager:
            raise self.retry(exc=exc)
        return None
    if email_id:
        with SessionLocal() as db:
            em = db.get(EmailMessage, email_id)
            if em:
                em.status, em.sent_at, em.message_id, em.error = "sent", utcnow(), msg_id, None
                db.commit()
    return msg_id


@celery.task(name="app.worker.tasks.send_telegram_task")
def send_telegram_task(chat_id: str, text: str):
    try:
        telegram.send_message(chat_id, text)
    except Exception:
        log.warning("Ошибка отправки в Telegram", exc_info=True)


@celery.task(name="app.worker.tasks.process_reminders")
def process_reminders():
    """Напоминания о задачах за 15 мин / 1 час / 1 день до срока."""
    from app.services.notify import notify

    now = utcnow()
    with SessionLocal() as db:
        tasks = db.scalars(select(Task).where(
            Task.status == "open", Task.reminder_minutes.is_not(None), Task.reminder_sent_at.is_(None),
            Task.due_at > now - timedelta(hours=1), Task.due_at <= now + timedelta(days=1, minutes=1))).unique().all()
        sent = 0
        for t in tasks:
            if t.due_at - timedelta(minutes=t.reminder_minutes) > now:
                continue
            minutes = max(int((t.due_at - now).total_seconds() // 60), 0)
            when = "сейчас" if minutes == 0 else (f"через {minutes} мин" if minutes < 120 else
                                                   f"через {round(minutes / 60)} ч")
            notify(db, t.assignee_id, f"Напоминание: {TASK_TYPES.get(t.type, 'Задача')} {when}", t.title,
                   link=f"/tasks?open={t.id}", kind="reminder")
            t.reminder_sent_at = now
            sent += 1
        db.commit()
    return sent


@celery.task(name="app.worker.tasks.stale_deals_digest")
def stale_deals_digest():
    """Ежедневно: сделки без активности 14+ дней — риск потерять клиента."""
    from app.services.analytics import stale_deals
    from app.services.notify import notify

    with SessionLocal() as db:
        by_owner: dict[int, list] = {}
        for d in stale_deals(db):
            if d.owner_id:
                by_owner.setdefault(d.owner_id, []).append(d)
        for owner_id, deals in by_owner.items():
            names = "; ".join(d.title for d in deals[:5])
            more = f" и ещё {len(deals) - 5}" if len(deals) > 5 else ""
            notify(db, owner_id, f"Сделки без активности: {len(deals)}",
                   f"Нет контакта более 14 дней: {names}{more}", link="/deals?stale=1", kind="warning")
        db.commit()
    return sum(len(v) for v in by_owner.values())


@celery.task(name="app.worker.tasks.send_scheduled_reports")
def send_scheduled_reports():
    """Еженедельно (по понедельникам) и ежемесячно (1-го числа) рассылает отчёты руководителям."""
    from app.services import analytics
    from app.services.documents import export_report

    today = date.today()
    with SessionLocal() as db:
        schedules = db.scalars(select(ReportSchedule).where(ReportSchedule.is_active.is_(True))).all()
        count = 0
        for s in schedules:
            if s.frequency == "weekly" and today.weekday() != 0:
                continue
            if s.frequency == "monthly" and today.day != 1:
                continue
            user = db.get(User, s.user_id)
            if user is None or not user.is_active:
                continue
            period = analytics.default_period("week" if s.frequency == "weekly" else "prev_month")
            report = analytics.build_report(db, s.report, period, analytics.make_scope(user))
            data, mime, ext = export_report(db, report, s.format)
            from app.services.storage import get_storage, make_key

            key = make_key("reports", f"report.{ext}")
            get_storage().put(key, data, mime)
            html = (f"<p>Здравствуйте, {user.full_name}!</p><p>Во вложении отчёт «{report['title']}» "
                    f"за период {period.label}.</p><p>— CRM</p>")
            send_email_task.delay(s.email, f"Отчёт: {report['title']} ({period.label})", html, None, None,
                                  [(f"{s.report}_{period.date_from}_{period.date_to}.{ext}", key, mime)])
            s.last_sent_at = utcnow()
            count += 1
        db.commit()
    return count


@celery.task(name="app.worker.tasks.poll_imap")
def poll_imap():
    """Входящие письма: известный контакт → лента активностей, неизвестный → новый лид (email-парсер)."""
    from app.services.journal import log_activity
    from app.services.leads import register_lead

    try:
        messages = mailer.fetch_unseen()
    except Exception:
        log.warning("IMAP недоступен", exc_info=True)
        return 0
    if not messages:
        return 0
    with SessionLocal() as db:
        for m in messages:
            contact = db.scalars(select(Contact).where(func.lower(Contact.email) == m["from_email"],
                                                       Contact.deleted_at.is_(None))).first()
            em = EmailMessage(direction="in", status="received", subject=m["subject"][:500] or "(без темы)",
                              body=m["body"], from_email=m["from_email"], to_email=mailer.settings.IMAP_USER,
                              message_id=m["message_id"], contact_id=contact.id if contact else None,
                              company_id=contact.company_id if contact else None, sent_at=utcnow())
            db.add(em)
            db.flush()
            if contact:
                log_activity(db, type="email_in", title=f"Входящее письмо: {em.subject}", body=m["body"][:3000],
                             object_type="contact", object_id=contact.id, contact_id=contact.id,
                             company_id=contact.company_id, meta={"email_id": em.id, "from": m["from_email"]},
                             touch_company=True)
                continue
            existing = db.scalars(select(Lead).where(func.lower(Lead.email) == m["from_email"],
                                                     Lead.status.in_(["new", "in_progress"]))).first()
            if existing:
                em.lead_id = existing.id
                log_activity(db, type="email_in", title=f"Входящее письмо: {em.subject}", body=m["body"][:3000],
                             object_type="lead", object_id=existing.id, lead_id=existing.id,
                             meta={"email_id": em.id})
                continue
            lead = register_lead(db, {
                "title": (m["subject"] or f"Письмо от {m['from_email']}")[:255],
                "contact_name": m["from_name"] or None, "email": m["from_email"], "message": m["body"][:5000],
            }, source_code="email")
            em.lead_id = lead.id
        db.commit()
    return len(messages)


@celery.task(name="app.worker.tasks.poll_telegram")
def poll_telegram():
    """Привязка Telegram-аккаунтов: пользователь отправляет боту /start <код из профиля>."""
    if not telegram.enabled():
        return 0
    with SessionLocal() as db:
        row = db.get(SystemSetting, "telegram_offset")
        offset = int(row.value) if row and row.value else 0
        try:
            updates = telegram.get_updates(offset)
        except Exception:
            log.warning("Telegram getUpdates failed", exc_info=True)
            return 0
        for upd in updates:
            offset = max(offset, upd["update_id"] + 1)
            msg = upd.get("message") or {}
            text = (msg.get("text") or "").strip()
            chat_id = str(msg.get("chat", {}).get("id", ""))
            if not text.startswith("/start") or not chat_id:
                continue
            code = text.removeprefix("/start").strip()
            user = db.scalars(select(User).where(User.telegram_link_code == code)).first() if code else None
            if user:
                user.telegram_chat_id = chat_id
                user.telegram_link_code = random_token(8)
                user.notify_telegram = True
                send_telegram_task.delay(chat_id, f"✅ {user.full_name}, уведомления CRM подключены.")
            else:
                send_telegram_task.delay(chat_id, "Откройте профиль в CRM и нажмите «Подключить Telegram».")
        if row is None:
            db.add(SystemSetting(key="telegram_offset", value=offset))
        else:
            row.value = offset
        db.commit()
    return len(updates)
