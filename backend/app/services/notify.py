"""Уведомления пользователей: в интерфейсе, по email, в Telegram."""
import logging
from html import escape

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Notification, User

log = logging.getLogger(__name__)


def enqueue(task, *args, **kwargs) -> None:
    """Постановка фоновой задачи; сбой брокера не должен ломать основной запрос."""
    try:
        task.delay(*args, **kwargs)
    except Exception:
        log.exception("Не удалось поставить задачу %s в очередь", getattr(task, "name", task))


def notify(
    db: Session,
    user_id: int | None,
    title: str,
    body: str | None = None,
    *,
    link: str | None = None,
    kind: str = "info",
    email: bool = True,
    telegram: bool = True,
) -> None:
    if not user_id:
        return
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return
    if user.notify_push:
        db.add(Notification(user_id=user.id, kind=kind, title=title, body=body, link=link))

    from app.worker import tasks  # ленивый импорт: избегаем циклической зависимости

    url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}{link}" if link else None
    if email and user.notify_email:
        html = f"<p><b>{escape(title)}</b></p><p>{escape(body or '')}</p>"
        if url:
            html += f'<p><a href="{url}">Открыть в CRM</a></p>'
        enqueue(tasks.send_email_task, user.email, f"CRM: {title}", html)
    if telegram and user.notify_telegram and user.telegram_chat_id:
        text = f"<b>{escape(title)}</b>\n{escape(body or '')}"
        if url:
            text += f"\n{url}"
        enqueue(tasks.send_telegram_task, user.telegram_chat_id, text)
