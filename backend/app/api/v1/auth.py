from datetime import timedelta

import jwt
import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_current_user
from app.core.config import settings
from app.core.permissions import permissions_for
from app.core.security import (
    create_2fa_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    random_token,
    validate_password_strength,
    verify_password,
)
from app.db.base import utcnow
from app.db.session import get_db
from app.models import RefreshToken, User
from app.schemas.users import (
    LoginIn,
    MeOut,
    PasswordChange,
    ProfileUpdate,
    RefreshIn,
    TokenOut,
    TotpCodeIn,
    TotpSetupOut,
    TwoFactorIn,
)
from app.services import telegram
from app.services.journal import audit

router = APIRouter(prefix="/auth", tags=["Аутентификация"])

MAX_FAILED = 5
LOCK_MINUTES = 15


def _issue_tokens(db: Session, user: User, request: Request) -> TokenOut:
    refresh, jti, expires = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, jti=jti, expires_at=expires,
                        user_agent=(request.headers.get("user-agent") or "")[:500], ip=client_ip(request)))
    user.last_login = utcnow()
    user.failed_logins = 0
    user.locked_until = None
    return TokenOut(access_token=create_access_token(user.id, user.role), refresh_token=refresh)


@router.post("/login", response_model=TokenOut, summary="Вход по email и паролю")
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.email == data.email.lower())).first()
    now = utcnow()
    if user and user.locked_until and user.locked_until > now:
        raise HTTPException(status.HTTP_423_LOCKED,
                            "Слишком много неудачных попыток. Учётная запись временно заблокирована на 15 минут")
    if user is None or not verify_password(data.password, user.password_hash):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= MAX_FAILED:
                user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            audit(db, user, "login_failed", f"Неудачная попытка входа: {data.email}", request=request)
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Учётная запись заблокирована администратором")
    if user.totp_enabled:
        return TokenOut(two_factor_required=True, two_factor_token=create_2fa_token(user.id))
    tokens = _issue_tokens(db, user, request)
    audit(db, user, "login", "Вход в систему", request=request)
    db.commit()
    return tokens


@router.post("/2fa", response_model=TokenOut, summary="Второй шаг входа: код из приложения-аутентификатора")
def login_2fa(data: TwoFactorIn, request: Request, db: Session = Depends(get_db)):
    try:
        payload = decode_token(data.token, "2fa")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Сессия входа истекла, войдите заново")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active or not user.totp_secret:
        raise HTTPException(401, "Неверный код")
    if not pyotp.TOTP(user.totp_secret).verify(data.code.strip(), valid_window=1):
        user.failed_logins += 1
        if user.failed_logins >= MAX_FAILED:
            user.locked_until = utcnow() + timedelta(minutes=LOCK_MINUTES)
        audit(db, user, "login_failed", "Неверный код 2FA", request=request)
        db.commit()
        raise HTTPException(401, "Неверный код")
    tokens = _issue_tokens(db, user, request)
    audit(db, user, "login", "Вход в систему (2FA)", request=request)
    db.commit()
    return tokens


@router.post("/refresh", response_model=TokenOut, summary="Обновление access-токена (ротация refresh)")
def refresh(data: RefreshIn, request: Request, db: Session = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token, "refresh")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Сессия истекла, войдите заново")
    row = db.scalars(select(RefreshToken).where(RefreshToken.jti == payload["jti"])).first()
    if row is None or row.revoked:
        if row is not None:
            # Повторное использование отозванного токена — признак кражи: отзываем все сессии
            for t in db.scalars(select(RefreshToken).where(RefreshToken.user_id == row.user_id)):
                t.revoked = True
            db.commit()
        raise HTTPException(401, "Сессия истекла, войдите заново")
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(401, "Учётная запись заблокирована")
    row.revoked = True
    tokens = _issue_tokens(db, user, request)
    db.commit()
    return tokens


@router.post("/logout", summary="Выход (отзыв refresh-токена)")
def logout(data: RefreshIn, db: Session = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token, "refresh")
        row = db.scalars(select(RefreshToken).where(RefreshToken.jti == payload["jti"])).first()
        if row:
            row.revoked = True
            db.commit()
    except jwt.InvalidTokenError:
        pass
    return {"detail": "ok"}


def me_out(user: User) -> MeOut:
    out = MeOut.model_validate(user)
    out.permissions = permissions_for(user.role)
    out.telegram_linked = bool(user.telegram_chat_id)
    return out


@router.get("/me", response_model=MeOut, summary="Текущий пользователь и его права")
def me(user: User = Depends(get_current_user)):
    return me_out(user)


@router.patch("/me", response_model=MeOut, summary="Изменение профиля")
def update_me(data: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    db.commit()
    return me_out(user)


@router.post("/me/password", summary="Смена пароля")
def change_password(data: PasswordChange, request: Request, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "Текущий пароль указан неверно")
    err = validate_password_strength(data.new_password)
    if err:
        raise HTTPException(422, err)
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    audit(db, user, "password_change", "Смена пароля", entity="user", entity_id=user.id, request=request)
    db.commit()
    return {"detail": "Пароль изменён"}


@router.post("/me/2fa/setup", response_model=TotpSetupOut, summary="Начать подключение 2FA")
def totp_setup(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    secret = pyotp.random_base32()
    user.totp_secret = secret
    user.totp_enabled = False
    db.commit()
    url = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=settings.APP_NAME)
    return TotpSetupOut(secret=secret, otpauth_url=url)


@router.post("/me/2fa/enable", summary="Подтвердить подключение 2FA кодом")
def totp_enable(data: TotpCodeIn, request: Request, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    if not user.totp_secret or not pyotp.TOTP(user.totp_secret).verify(data.code.strip(), valid_window=1):
        raise HTTPException(400, "Неверный код")
    user.totp_enabled = True
    audit(db, user, "2fa_enabled", "Включена двухфакторная аутентификация", request=request)
    db.commit()
    return {"detail": "Двухфакторная аутентификация включена"}


@router.post("/me/2fa/disable", summary="Отключить 2FA")
def totp_disable(data: TotpCodeIn, request: Request, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    if user.totp_enabled and not pyotp.TOTP(user.totp_secret).verify(data.code.strip(), valid_window=1):
        raise HTTPException(400, "Неверный код")
    user.totp_enabled = False
    user.totp_secret = None
    audit(db, user, "2fa_disabled", "Отключена двухфакторная аутентификация", request=request)
    db.commit()
    return {"detail": "Двухфакторная аутентификация отключена"}


@router.post("/me/telegram", summary="Получить ссылку для подключения Telegram-бота")
def telegram_link(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not telegram.enabled():
        raise HTTPException(400, "Telegram-бот не настроен администратором (TELEGRAM_BOT_TOKEN)")
    user.telegram_link_code = random_token(8)
    db.commit()
    username = telegram.bot_username()
    return {"code": user.telegram_link_code,
            "url": f"https://t.me/{username}?start={user.telegram_link_code}" if username else None}


@router.delete("/me/telegram", summary="Отключить Telegram")
def telegram_unlink(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.telegram_chat_id = None
    user.notify_telegram = False
    db.commit()
    return {"detail": "Telegram отключён"}
