from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORM, UserRef
from app.schemas.crm import CompanyShort, ContactShort


class FileOut(ORM):
    id: int
    deal_id: int | None
    company_id: int | None
    doc_type: str
    name: str
    content_type: str | None
    size: int
    uploader: UserRef | None
    created_at: datetime


class TemplateOut(ORM):
    id: int
    name: str
    industry_id: int | None
    description: str | None
    intro_text: str
    terms_text: str
    footer_text: str
    accent_color: str
    default_items: list
    is_active: bool


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    industry_id: int | None = None
    description: str | None = None
    intro_text: str = ""
    terms_text: str = ""
    footer_text: str = ""
    accent_color: str = "#1c7ed6"
    default_items: list = []
    is_active: bool = True


class LineIn(BaseModel):
    product_id: int | None = None
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    quantity: float = Field(gt=0, default=1)
    unit: str = "шт."
    price: float = Field(ge=0, default=0)
    discount_percent: float = Field(ge=0, le=100, default=0)


class LineOut(ORM):
    id: int | None = None
    product_id: int | None = None
    name: str
    description: str | None = None
    quantity: float
    unit: str
    price: float
    discount_percent: float
    total: float


class ProposalCreate(BaseModel):
    deal_id: int | None = None
    company_id: int | None = None
    contact_id: int | None = None
    template_id: int | None = None
    title: str | None = None
    currency: str = "RUB"
    vat_rate: int = 20
    valid_until: date | None = None
    intro_text: str | None = None
    terms_text: str | None = None
    items: list[LineIn] | None = None


class ProposalUpdate(BaseModel):
    title: str | None = None
    contact_id: int | None = None
    currency: str | None = None
    vat_rate: int | None = None
    valid_until: date | None = None
    intro_text: str | None = None
    terms_text: str | None = None
    items: list[LineIn] | None = None
    status: Literal["draft", "sent", "viewed", "approved", "rejected"] | None = None


class ProposalSend(BaseModel):
    to: EmailStr
    subject: str | None = None
    message: str | None = None


class ProposalOut(ORM):
    id: int
    number: str
    title: str
    deal_id: int | None
    company: CompanyShort | None
    contact: ContactShort | None
    template_id: int | None
    owner: UserRef | None
    status: str
    currency: str
    vat_rate: int
    valid_until: date | None
    intro_text: str
    terms_text: str
    total: float
    sent_to: str | None
    sent_at: datetime | None
    viewed_at: datetime | None
    decided_at: datetime | None
    client_comment: str | None
    created_at: datetime
    public_url: str | None = None


class ProposalDetail(ProposalOut):
    items: list[LineOut]


class PublicDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: str | None = Field(default=None, max_length=2000)


# ---------- Счета, оплаты, акты ----------

class InvoiceCreate(BaseModel):
    deal_id: int | None = None
    company_id: int | None = None
    proposal_id: int | None = None
    issued_at: date | None = None
    due_date: date | None = None
    vat_rate: int = 20
    currency: str = "RUB"
    items: list[LineIn] | None = None
    comment: str | None = None


class InvoiceUpdate(BaseModel):
    due_date: date | None = None
    comment: str | None = None
    status: Literal["draft", "issued", "canceled"] | None = None


class PaymentIn(BaseModel):
    amount: float = Field(gt=0)
    paid_at: date
    comment: str | None = None


class PaymentOut(ORM):
    id: int
    amount: float
    paid_at: date
    comment: str | None


class InvoiceOut(ORM):
    id: int
    number: str
    deal_id: int | None
    company: CompanyShort | None
    owner: UserRef | None
    issued_at: date
    due_date: date
    currency: str
    vat_rate: int
    items: list
    amount: float
    paid_amount: float
    status: str
    paid_at: date | None
    comment: str | None
    exported_1c_at: datetime | None
    created_at: datetime
    is_overdue: bool = False
    debt: float = 0


class InvoiceDetail(InvoiceOut):
    payments: list[PaymentOut]


class ActOut(ORM):
    id: int
    number: str
    invoice_id: int | None
    deal_id: int | None
    company: CompanyShort | None
    act_date: date
    amount: float
    vat_rate: int
    items: list
    status: str
    exported_1c_at: datetime | None
    created_at: datetime


class ActCreate(BaseModel):
    invoice_id: int
    act_date: date | None = None


class ActUpdate(BaseModel):
    status: Literal["draft", "sent", "signed"]


class ReportScheduleIn(BaseModel):
    report: Literal["summary", "funnel", "managers", "sources", "products", "receivables"]
    frequency: Literal["weekly", "monthly"]
    format: Literal["pdf", "xlsx", "csv"] = "pdf"
    email: EmailStr
    is_active: bool = True


class ReportScheduleOut(ORM):
    id: int
    report: str
    frequency: str
    format: str
    email: str
    is_active: bool
    last_sent_at: datetime | None
    created_at: datetime
