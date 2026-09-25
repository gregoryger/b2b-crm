"""Регистрация лидов и распределение по менеджерам."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import Role
from app.core.security import phone_hash
from app.models import DictionaryItem, Lead, User
from app.services.common import get_setting, set_setting
from app.services.journal import log_activity
from app.services.notify import notify

SOURCE_LABELS = {"website": "Форма сайта", "email": "Email", "manual": "Ручной ввод", "api": "API", "phone": "Телефон"}


def source_by_code(db: Session, code: str | None) -> DictionaryItem | None:
    if not code:
        return None
    item = db.scalars(select(DictionaryItem).where(DictionaryItem.kind == "lead_source",
                                                   DictionaryItem.code == code)).first()
    if item is None and code in SOURCE_LABELS:
        item = DictionaryItem(kind="lead_source", code=code, name=SOURCE_LABELS[code], sort=100)
        db.add(item)
        db.flush()
    return item


def pick_manager(db: Session) -> int | None:
    """Автораспределение: по кругу или на наименее загруженного менеджера."""
    cfg = get_setting(db, "lead_distribution")
    mode = cfg.get("mode", "round_robin")
    if mode == "off":
        return None
    q = select(User.id).where(User.is_active.is_(True), User.role == Role.manager.value).order_by(User.id)
    if cfg.get("user_ids"):
        q = q.where(User.id.in_(cfg["user_ids"]))
    managers = list(db.scalars(q))
    if not managers:
        return None
    if mode == "least_loaded":
        loads = dict(db.execute(
            select(Lead.assigned_to, func.count()).where(Lead.status.in_(["new", "in_progress"]),
                                                         Lead.deleted_at.is_(None))
            .group_by(Lead.assigned_to)).all())
        return min(managers, key=lambda uid: loads.get(uid, 0))
    idx = (int(cfg.get("last_index", -1)) + 1) % len(managers)
    set_setting(db, "lead_distribution", {**cfg, "last_index": idx})
    return managers[idx]


def register_lead(db: Session, data: dict, *, source_code: str | None = None, user: User | None = None) -> Lead:
    if source_code and not data.get("source_id"):
        src = source_by_code(db, source_code)
        data["source_id"] = src.id if src else None
    if not data.get("assigned_to"):
        if user is not None and user.role == Role.manager.value:
            data["assigned_to"] = user.id
        else:
            data["assigned_to"] = pick_manager(db)
    lead = Lead(**data)
    lead.phone_hash = phone_hash(lead.phone)
    db.add(lead)
    db.flush()
    log_activity(db, type="created", title="Лид создан", object_type="lead", object_id=lead.id, user=user,
                 lead_id=lead.id, meta={"source": source_code})
    if lead.assigned_to and (user is None or lead.assigned_to != user.id):
        notify(db, lead.assigned_to, "Новый лид", f"{lead.title}. {lead.company_name or ''} {lead.phone or ''}".strip(),
               link=f"/leads/{lead.id}", kind="lead")
    return lead
