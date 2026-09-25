import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from app.core.config import settings

ALGORITHM = "HS256"


# ---------- Пароли ----------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def validate_password_strength(password: str) -> str | None:
    if len(password) < 8:
        return "Пароль должен быть не короче 8 символов"
    if not re.search(r"[A-Za-zА-Яа-я]", password) or not re.search(r"\d", password):
        return "Пароль должен содержать буквы и цифры"
    return None


def generate_password(length: int = 12) -> str:
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if validate_password_strength(pwd) is None:
            return pwd


# ---------- JWT ----------

def _encode(payload: dict, expires: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {**payload, "iat": now, "exp": now + expires}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: int, role: str) -> str:
    return _encode({"sub": str(user_id), "role": role, "type": "access"},
                   timedelta(minutes=settings.ACCESS_TOKEN_MINUTES))


def create_refresh_token(user_id: int) -> tuple[str, str, datetime]:
    jti = uuid.uuid4().hex
    expires = timedelta(days=settings.REFRESH_TOKEN_DAYS)
    token = _encode({"sub": str(user_id), "type": "refresh", "jti": jti}, expires)
    return token, jti, datetime.now(timezone.utc) + expires


def create_2fa_token(user_id: int) -> str:
    return _encode({"sub": str(user_id), "type": "2fa"}, timedelta(minutes=5))


def decode_token(token: str, expected_type: str) -> dict:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def random_token(nbytes: int = 24) -> str:
    return secrets.token_urlsafe(nbytes)


# ---------- Шифрование чувствительных полей ----------

_fernet = Fernet(settings.FIELD_ENCRYPTION_KEY.encode())


class EncryptedString(TypeDecorator):
    """Строка, хранимая в БД в зашифрованном виде (Fernet / AES-128-CBC + HMAC)."""

    impl = String
    cache_ok = True

    def __init__(self, length: int = 512, **kw):
        super().__init__(length, **kw)

    def process_bind_param(self, value, dialect):
        if value is None or value == "":
            return value
        return _fernet.encrypt(str(value).encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None or value == "":
            return value
        try:
            return _fernet.decrypt(value.encode()).decode()
        except InvalidToken:
            return value


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    return digits or None


def phone_hash(phone: str | None) -> str | None:
    """Слепой индекс: позволяет искать по телефону, не храня его в открытом виде."""
    norm = normalize_phone(phone)
    if not norm:
        return None
    return hmac.new(settings.SECRET_KEY.encode(), norm.encode(), hashlib.sha256).hexdigest()[:40]
