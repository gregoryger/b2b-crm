from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require
from app.core.permissions import PERMISSIONS, ROLE_LABELS, Role
from app.core.security import generate_password, hash_password, validate_password_strength
from app.db.session import get_db
from app.models import Notification, RefreshToken, User
from app.schemas.common import UserRef
from app.schemas.users import NotificationOut, UserCreate, UserOut, UserUpdate
from app.services.journal import audit
from app.services.notify import enqueue

router = APIRouter(tags=["Пользователи"])


@router.get("/users/lookup", response_model=list[UserRef], summary="Список активных сотрудников (для выбора)")
def lookup(role: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(User).where(User.is_active.is_(True)).order_by(User.full_name)
    if role:
        q = q.where(User.role.in_(role.split(",")))
    return db.scalars(q).all()


@router.get("/users/roles", summary="Ролевая модель: роли и права")
def roles(user: User = Depends(get_current_user)):
    return {
        "roles": [{"value": r.value, "label": ROLE_LABELS[r]} for r in Role],
        "matrix": {perm: sorted(r.value for r in rs) for perm, rs in PERMISSIONS.items()},
    }


@router.get("/users", response_model=list[UserOut], summary="Все пользователи")
def list_users(q: str | None = None, role: str | None = None, is_active: bool | None = None,
               user: User = Depends(require("users.manage")), db: Session = Depends(get_db)):
    stmt = select(User).order_by(User.is_active.desc(), User.full_name)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(User.full_name).like(like), func.lower(User.email).like(like)))
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    return db.scalars(stmt).all()


def _send_credentials(user: User, password: str, reason: str) -> None:
    from app.core.config import settings
    from app.worker.tasks import send_email_task

    html = (f"<p>Здравствуйте, {user.full_name}!</p><p>{reason}</p>"
            f"<p>Адрес: <a href='{settings.PUBLIC_BASE_URL}'>{settings.PUBLIC_BASE_URL}</a><br>"
            f"Логин: <b>{user.email}</b><br>Временный пароль: <b>{password}</b></p>"
            f"<p>При первом входе система попросит сменить пароль.</p>")
    enqueue(send_email_task, user.email, "Доступ к CRM", html)


@router.post("/users", response_model=dict, status_code=201, summary="Создать пользователя")
def create_user(data: UserCreate, request: Request, admin: User = Depends(require("users.manage")),
                db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.scalars(select(User).where(User.email == email)).first():
        raise HTTPException(409, "Пользователь с таким email уже существует")
    password = data.password or generate_password()
    err = validate_password_strength(password)
    if err:
        raise HTTPException(422, err)
    user = User(email=email, full_name=data.full_name, role=data.role.value, position=data.position,
                phone=data.phone, department=data.department, sip_extension=data.sip_extension,
                password_hash=hash_password(password), must_change_password=True)
    db.add(user)
    db.flush()
    audit(db, admin, "user_create", f"Создан пользователь {email} ({ROLE_LABELS[data.role]})", entity="user",
          entity_id=user.id, request=request)
    db.commit()
    _send_credentials(user, password, "Для вас создана учётная запись в CRM.")
    return {"user": UserOut.model_validate(user).model_dump(mode="json"), "temporary_password": password}


@router.patch("/users/{user_id}", response_model=UserOut, summary="Изменить пользователя / заблокировать")
def update_user(user_id: int, data: UserUpdate, request: Request, admin: User = Depends(require("users.manage")),
                db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Пользователь не найден")
    values = data.model_dump(exclude_unset=True)
    if user.id == admin.id and (values.get("is_active") is False or
                                ("role" in values and values["role"] != Role.admin)):
        raise HTTPException(400, "Нельзя заблокировать себя или снять с себя роль администратора")
    if "email" in values:
        values["email"] = values["email"].lower()
        other = db.scalars(select(User).where(User.email == values["email"], User.id != user.id)).first()
        if other:
            raise HTTPException(409, "Email уже используется")
    if "role" in values and values["role"] is not None:
        values["role"] = Role(values["role"]).value
    changes = {k: [getattr(user, k), v] for k, v in values.items() if getattr(user, k) != v and k != "phone"}
    for k, v in values.items():
        setattr(user, k, v)
    if values.get("is_active") is False:
        db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked=True))
        audit(db, admin, "user_block", f"Заблокирован пользователь {user.email}", entity="user", entity_id=user.id,
              request=request)
    elif changes:
        action = "role_change" if "role" in changes else "user_update"
        audit(db, admin, action, f"Изменён пользователь {user.email}", entity="user", entity_id=user.id,
              changes=changes, request=request)
    db.commit()
    return user


@router.post("/users/{user_id}/reset-password", summary="Сбросить пароль (временный пароль уходит на email)")
def reset_password(user_id: int, request: Request, admin: User = Depends(require("users.manage")),
                   db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Пользователь не найден")
    password = generate_password()
    user.password_hash = hash_password(password)
    user.must_change_password = True
    user.failed_logins = 0
    user.locked_until = None
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked=True))
    audit(db, admin, "password_reset", f"Сброшен пароль пользователя {user.email}", entity="user",
          entity_id=user.id, request=request)
    db.commit()
    _send_credentials(user, password, "Администратор сбросил ваш пароль.")
    return {"temporary_password": password}


@router.post("/users/{user_id}/reset-2fa", summary="Отключить 2FA пользователю (при утере телефона)")
def reset_2fa(user_id: int, request: Request, admin: User = Depends(require("users.manage")),
              db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Пользователь не найден")
    user.totp_enabled = False
    user.totp_secret = None
    audit(db, admin, "2fa_reset", f"Сброшена 2FA пользователя {user.email}", entity="user", entity_id=user.id,
          request=request)
    db.commit()
    return {"detail": "2FA отключена"}


# ---------- Уведомления ----------

@router.get("/notifications", response_model=list[NotificationOut], tags=["Уведомления"])
def notifications(unread: bool = False, limit: int = 30, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    q = select(Notification).where(Notification.user_id == user.id)
    if unread:
        q = q.where(Notification.is_read.is_(False))
    return db.scalars(q.order_by(Notification.created_at.desc()).limit(min(limit, 100))).all()


@router.get("/notifications/unread-count", tags=["Уведомления"])
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    count = db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id, Notification.is_read.is_(False)))
    latest = db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False))
                        .order_by(Notification.id.desc()).limit(1)).first()
    return {"count": count or 0, "latest_id": latest.id if latest else None}


@router.post("/notifications/read", tags=["Уведомления"])
def mark_read(ids: list[int] | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = update(Notification).where(Notification.user_id == user.id)
    if ids:
        stmt = stmt.where(Notification.id.in_(ids))
    db.execute(stmt.values(is_read=True))
    db.commit()
    return {"detail": "ok"}
