from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORM


class DictionaryItemOut(ORM):
    id: int
    kind: str
    name: str
    code: str | None
    sort: int
    is_active: bool


class DictionaryItemIn(BaseModel):
    kind: Literal["industry", "region", "client_type", "lead_source", "loss_reason"]
    name: str = Field(min_length=1, max_length=255)
    code: str | None = None
    sort: int = 0
    is_active: bool = True


class DictionaryItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sort: int | None = None
    is_active: bool | None = None


class StageOut(ORM):
    id: int
    name: str
    sort: int
    probability: int
    color: str
    kind: str
    is_active: bool


class StageIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    sort: int = 0
    probability: int = Field(ge=0, le=100, default=0)
    color: str = "blue"
    kind: Literal["open", "won", "lost"] = "open"
    is_active: bool = True


class StageOrderIn(BaseModel):
    ids: list[int]


class ProductOut(ORM):
    id: int
    name: str
    sku: str | None
    category: str | None
    unit: str
    price: float
    cost: float
    currency: str
    vat_rate: int
    description: str | None
    is_active: bool


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    sku: str | None = None
    category: str | None = None
    unit: str = "шт."
    price: float = Field(ge=0, default=0)
    cost: float = Field(ge=0, default=0)
    currency: str = "RUB"
    vat_rate: int = 20
    description: str | None = None
    is_active: bool = True


class CustomFieldOut(ORM):
    id: int
    entity: str
    key: str
    label: str
    field_type: str
    options: list[str] | None
    required: bool
    sort: int
    is_active: bool


class CustomFieldIn(BaseModel):
    entity: Literal["company", "contact", "deal", "lead"]
    label: str = Field(min_length=1, max_length=255)
    field_type: Literal["text", "number", "date", "select", "checkbox"]
    options: list[str] | None = None
    required: bool = False
    sort: int = 0
    is_active: bool = True


class CustomFieldUpdate(BaseModel):
    label: str | None = None
    options: list[str] | None = None
    required: bool | None = None
    sort: int | None = None
    is_active: bool | None = None


class MarketingSpendOut(ORM):
    id: int
    source_id: int
    month: date
    amount: float
    comment: str | None


class MarketingSpendIn(BaseModel):
    source_id: int
    month: date
    amount: float = Field(ge=0)
    comment: str | None = None
