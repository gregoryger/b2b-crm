from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, EmailStr, Field

from app.schemas.common import ORM, Ref, StageRef, UserRef

CompanyStatus = Literal["prospect", "active", "inactive", "partner"]
ContactRole = Literal["decision_maker", "influencer", "technical", "other"]
LeadStatus = Literal["new", "in_progress", "qualified", "rejected"]


def _empty_to_none(v):
    return None if isinstance(v, str) and not v.strip() else v


# Пустая строка из формы трактуется как «не заполнено»
OptStr = Annotated[str | None, BeforeValidator(_empty_to_none)]
OptEmail = Annotated[EmailStr | None, BeforeValidator(_empty_to_none)]


# ---------- Компании ----------

class CompanyBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    full_name: str | None = None
    inn: Annotated[OptStr, Field(max_length=12)] = None
    kpp: Annotated[OptStr, Field(max_length=9)] = None
    ogrn: Annotated[OptStr, Field(max_length=15)] = None
    legal_address: str | None = None
    actual_address: str | None = None
    bank_name: str | None = None
    bik: Annotated[OptStr, Field(max_length=9)] = None
    account: Annotated[OptStr, Field(max_length=20)] = None
    corr_account: Annotated[OptStr, Field(max_length=20)] = None
    industry_id: int | None = None
    region_id: int | None = None
    client_type_id: int | None = None
    source_id: int | None = None
    manager_id: int | None = None
    status: CompanyStatus = "prospect"
    phone: OptStr = None
    email: OptEmail = None
    website: str | None = None
    description: str | None = None
    custom_fields: dict = {}


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(CompanyBase):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: CompanyStatus | None = None
    custom_fields: dict | None = None


class CompanyShort(ORM):
    id: int
    name: str
    inn: OptStr = None


class CompanyOut(ORM):
    id: int
    name: str
    full_name: str | None
    inn: str | None
    kpp: str | None
    ogrn: str | None
    legal_address: str | None
    actual_address: str | None
    bank_name: str | None
    bik: str | None
    account: str | None
    corr_account: str | None
    industry: Ref | None
    region: Ref | None
    client_type: Ref | None
    source: Ref | None
    manager: UserRef | None
    status: str
    phone: str | None
    email: str | None
    website: str | None
    description: str | None
    custom_fields: dict
    last_contact_at: datetime | None
    created_at: datetime
    updated_at: datetime
    total_revenue: float = 0
    open_deals: int = 0


# ---------- Контакты ----------

class ContactBase(BaseModel):
    company_id: int | None = None
    last_name: str = Field(min_length=1, max_length=100)
    first_name: str = Field(min_length=1, max_length=100)
    middle_name: str | None = None
    position: str | None = None
    phone_mobile: OptStr = None
    phone_work: OptStr = None
    email: OptEmail = None
    telegram: str | None = None
    whatsapp: str | None = None
    role_in_deal: Annotated[ContactRole | None, BeforeValidator(_empty_to_none)] = None
    notes: str | None = None
    owner_id: int | None = None
    custom_fields: dict = {}


class ContactCreate(ContactBase):
    pass


class ContactUpdate(ContactBase):
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    custom_fields: dict | None = None


class ContactOut(ORM):
    id: int
    company: CompanyShort | None
    owner: UserRef | None
    last_name: str
    first_name: str
    middle_name: str | None
    full_name: str
    position: str | None
    phone_mobile: str | None
    phone_work: str | None
    email: str | None
    telegram: str | None
    whatsapp: str | None
    role_in_deal: str | None
    notes: str | None
    custom_fields: dict
    created_at: datetime


class ContactShort(ORM):
    id: int
    full_name: str
    position: str | None = None
    email: str | None = None
    phone_mobile: OptStr = None


# ---------- Лиды ----------

class LeadBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    source_id: int | None = None
    assigned_to: int | None = None
    company_name: str | None = None
    inn: OptStr = None
    contact_name: str | None = None
    contact_position: str | None = None
    phone: OptStr = None
    email: OptEmail = None
    message: str | None = None
    estimated_amount: float | None = Field(default=None, ge=0)
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    custom_fields: dict = {}


class LeadCreate(LeadBase):
    pass


class LeadUpdate(LeadBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    status: Literal["new", "in_progress"] | None = None
    custom_fields: dict | None = None


class LeadReject(BaseModel):
    reason_id: int
    comment: str | None = None


class LeadConvert(BaseModel):
    company_id: int | None = None  # существующая компания; иначе будет создана новая
    company_name: str | None = None
    inn: OptStr = None
    contact_id: int | None = None
    create_contact: bool = True
    deal_title: str | None = None
    amount: float = Field(ge=0, default=0)
    stage_id: int | None = None
    close_date: date | None = None


class PublicLeadIn(BaseModel):
    """Приём заявок с сайта (REST endpoint для веб-форм)."""
    name: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    phone: Annotated[OptStr, Field(max_length=50)] = None
    email: OptEmail = None
    message: str | None = Field(default=None, max_length=5000)
    inn: Annotated[OptStr, Field(max_length=12)] = None
    source: str | None = Field(default=None, max_length=64, description="Код источника, по умолчанию website")
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None


class LeadOut(ORM):
    id: int
    title: str
    source: Ref | None
    status: str
    reject_reason: Ref | None
    reject_comment: str | None
    assignee: UserRef | None
    company_name: str | None
    inn: str | None
    contact_name: str | None
    contact_position: str | None
    phone: str | None
    email: str | None
    message: str | None
    estimated_amount: float | None
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    custom_fields: dict
    company_id: int | None
    contact_id: int | None
    deal_id: int | None
    first_response_at: datetime | None
    qualified_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ---------- Сделки ----------

class DealProductIn(BaseModel):
    product_id: int | None = None
    name: str = Field(min_length=1, max_length=255)
    quantity: float = Field(gt=0, default=1)
    unit: str = "шт."
    price: float = Field(ge=0, default=0)
    discount_percent: float = Field(ge=0, le=100, default=0)


class DealProductOut(ORM):
    id: int
    product_id: int | None
    name: str
    quantity: float
    unit: str
    price: float
    discount_percent: float
    total: float


class DealContactIn(BaseModel):
    contact_id: int
    role: ContactRole | None = None


class DealContactOut(ORM):
    contact: ContactShort
    role: str | None


class DealMemberIn(BaseModel):
    user_id: int
    role: str | None = None


class DealMemberOut(ORM):
    user: UserRef
    role: str | None


class DealBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    company_id: int | None = None
    contact_id: int | None = None
    owner_id: int | None = None
    stage_id: int | None = None
    amount: float = Field(ge=0, default=0)
    currency: Literal["RUB", "USD", "EUR", "CNY"] = "RUB"
    probability: int | None = Field(default=None, ge=0, le=100)
    close_date: date | None = None
    description: str | None = None
    custom_fields: dict = {}
    products: list[DealProductIn] | None = None
    contacts: list[DealContactIn] | None = None
    members: list[DealMemberIn] | None = None


class DealCreate(DealBase):
    pass


class DealUpdate(DealBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    amount: float | None = Field(default=None, ge=0)
    currency: Literal["RUB", "USD", "EUR", "CNY"] | None = None
    custom_fields: dict | None = None


class DealMove(BaseModel):
    stage_id: int
    lost_reason_id: int | None = None
    lost_comment: str | None = None


class DealOut(ORM):
    id: int
    title: str
    company: CompanyShort | None
    contact: ContactShort | None
    owner: UserRef | None
    stage: StageRef
    lead_id: int | None
    amount: float
    currency: str
    probability: int
    close_date: date | None
    status: str
    closed_at: datetime | None
    lost_reason: Ref | None
    lost_comment: str | None
    description: str | None
    custom_fields: dict
    stage_changed_at: datetime
    created_at: datetime
    updated_at: datetime


class DealDetail(DealOut):
    products: list[DealProductOut]
    contacts: list[DealContactOut]
    members: list[DealMemberOut]


class BulkAssign(BaseModel):
    ids: list[int]
    user_id: int
