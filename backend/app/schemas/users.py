from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.core.permissions import Role
from app.schemas.common import ORM


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TwoFactorIn(BaseModel):
    token: str
    code: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    two_factor_required: bool = False
    two_factor_token: str | None = None


class UserOut(ORM):
    id: int
    email: str
    full_name: str
    position: str | None
    phone: str | None
    role: Role
    department: str | None
    is_active: bool
    last_login: datetime | None
    created_at: datetime
    sip_extension: str | None
    totp_enabled: bool


class MeOut(UserOut):
    permissions: list[str] = []
    must_change_password: bool
    onboarding_done: bool
    notify_push: bool
    notify_email: bool
    notify_telegram: bool
    telegram_linked: bool = False
    telegram_link_code: str | None = None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    role: Role
    position: str | None = None
    phone: str | None = None
    department: str | None = None
    sip_extension: str | None = None
    password: str | None = None


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    role: Role | None = None
    position: str | None = None
    phone: str | None = None
    department: str | None = None
    sip_extension: str | None = None
    is_active: bool | None = None


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    position: str | None = None
    phone: str | None = None
    notify_push: bool | None = None
    notify_email: bool | None = None
    notify_telegram: bool | None = None
    onboarding_done: bool | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class TotpSetupOut(BaseModel):
    secret: str
    otpauth_url: str


class TotpCodeIn(BaseModel):
    code: str


class NotificationOut(ORM):
    id: int
    kind: str
    title: str
    body: str | None
    link: str | None
    is_read: bool
    created_at: datetime


class ApiKeyOut(ORM):
    id: int
    name: str
    prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None


class ApiKeyCreated(ApiKeyOut):
    key: str
