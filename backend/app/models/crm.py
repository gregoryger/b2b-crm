from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import EncryptedString
from app.db.base import Base, JSONType, TimestampMixin, utcnow
from app.models.reference import DictionaryItem, PipelineStage
from app.models.user import User


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    full_name: Mapped[str | None] = mapped_column(String(512))
    inn: Mapped[str | None] = mapped_column(String(12), index=True)
    kpp: Mapped[str | None] = mapped_column(String(9))
    ogrn: Mapped[str | None] = mapped_column(String(15))
    legal_address: Mapped[str | None] = mapped_column(Text)
    actual_address: Mapped[str | None] = mapped_column(Text)
    bank_name: Mapped[str | None] = mapped_column(String(255))
    bik: Mapped[str | None] = mapped_column(String(9))
    account: Mapped[str | None] = mapped_column(String(20))
    corr_account: Mapped[str | None] = mapped_column(String(20))

    industry_id: Mapped[int | None] = mapped_column(ForeignKey("dictionary_items.id", ondelete="SET NULL"), index=True)
    region_id: Mapped[int | None] = mapped_column(ForeignKey("dictionary_items.id", ondelete="SET NULL"), index=True)
    client_type_id: Mapped[int | None] = mapped_column(ForeignKey("dictionary_items.id", ondelete="SET NULL"))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("dictionary_items.id", ondelete="SET NULL"))
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="prospect", index=True)  # prospect|active|inactive|partner

    phone: Mapped[str | None] = mapped_column(EncryptedString())
    phone_hash: Mapped[str | None] = mapped_column(String(40), index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    website: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    custom_fields: Mapped[dict] = mapped_column(JSONType, default=dict)
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    # selectin, а не joined: компания часто подгружается как вложенный объект (сделка, контакт, счёт),
    # и каскад JOIN'ов по её справочникам сильно утяжелял запросы списков
    manager: Mapped[User | None] = relationship(lazy="selectin", foreign_keys=[manager_id])
    industry: Mapped[DictionaryItem | None] = relationship(lazy="selectin", foreign_keys=[industry_id])
    region: Mapped[DictionaryItem | None] = relationship(lazy="selectin", foreign_keys=[region_id])
    client_type: Mapped[DictionaryItem | None] = relationship(lazy="selectin", foreign_keys=[client_type_id])
    source: Mapped[DictionaryItem | None] = relationship(lazy="selectin", foreign_keys=[source_id])


class Contact(TimestampMixin, Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), index=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    last_name: Mapped[str] = mapped_column(String(100))
    first_name: Mapped[str] = mapped_column(String(100))
    middle_name: Mapped[str | None] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(320), index=True)
    position: Mapped[str | None] = mapped_column(String(255))
    phone_mobile: Mapped[str | None] = mapped_column(EncryptedString())
    phone_mobile_hash: Mapped[str | None] = mapped_column(String(40), index=True)
    phone_work: Mapped[str | None] = mapped_column(EncryptedString())
    phone_work_hash: Mapped[str | None] = mapped_column(String(40), index=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    telegram: Mapped[str | None] = mapped_column(String(100))
    whatsapp: Mapped[str | None] = mapped_column(String(100))
    role_in_deal: Mapped[str | None] = mapped_column(String(20))  # decision_maker|influencer|technical|other
    notes: Mapped[str | None] = mapped_column(Text)
    custom_fields: Mapped[dict] = mapped_column(JSONType, default=dict)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    company: Mapped[Company | None] = relationship(lazy="selectin")
    owner: Mapped[User | None] = relationship(lazy="selectin")


class Lead(TimestampMixin, Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("dictionary_items.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)  # new|in_progress|qualified|rejected
    reject_reason_id: Mapped[int | None] = mapped_column(ForeignKey("dictionary_items.id", ondelete="SET NULL"))
    reject_comment: Mapped[str | None] = mapped_column(Text)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    company_name: Mapped[str | None] = mapped_column(String(255))
    inn: Mapped[str | None] = mapped_column(String(12))
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_position: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(EncryptedString())
    phone_hash: Mapped[str | None] = mapped_column(String(40), index=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    message: Mapped[str | None] = mapped_column(Text)
    estimated_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    utm_source: Mapped[str | None] = mapped_column(String(255))
    utm_medium: Mapped[str | None] = mapped_column(String(255))
    utm_campaign: Mapped[str | None] = mapped_column(String(255))
    custom_fields: Mapped[dict] = mapped_column(JSONType, default=dict)

    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"))
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="SET NULL", use_alter=True))
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    source: Mapped[DictionaryItem | None] = relationship(lazy="joined", foreign_keys=[source_id])
    reject_reason: Mapped[DictionaryItem | None] = relationship(lazy="joined", foreign_keys=[reject_reason_id])
    assignee: Mapped[User | None] = relationship(lazy="joined", foreign_keys=[assigned_to])


class Deal(TimestampMixin, Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), index=True)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"))
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"))
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    stage_id: Mapped[int] = mapped_column(ForeignKey("pipeline_stages.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    probability: Mapped[int] = mapped_column(Integer, default=0)
    close_date: Mapped[date | None] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)  # open|won|lost
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    lost_reason_id: Mapped[int | None] = mapped_column(ForeignKey("dictionary_items.id", ondelete="SET NULL"))
    lost_comment: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    custom_fields: Mapped[dict] = mapped_column(JSONType, default=dict)
    stage_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    company: Mapped[Company | None] = relationship(lazy="joined")
    contact: Mapped[Contact | None] = relationship(lazy="joined")
    owner: Mapped[User | None] = relationship(lazy="joined")
    stage: Mapped[PipelineStage] = relationship(lazy="joined")
    lost_reason: Mapped[DictionaryItem | None] = relationship(lazy="joined")
    products: Mapped[list["DealProduct"]] = relationship(
        back_populates="deal", cascade="all, delete-orphan", lazy="selectin", order_by="DealProduct.id")
    contacts: Mapped[list["DealContact"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    members: Mapped[list["DealMember"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class DealProduct(Base):
    __tablename__ = "deal_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=1)
    unit: Mapped[str] = mapped_column(String(20), default="шт.")
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)

    deal: Mapped[Deal] = relationship(back_populates="products")

    @property
    def total(self) -> Decimal:
        return (Decimal(self.quantity) * Decimal(self.price) * (1 - Decimal(self.discount_percent) / 100)).quantize(Decimal("0.01"))


class DealContact(Base):
    """Участники сделки со стороны клиента."""

    __tablename__ = "deal_contacts"

    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str | None] = mapped_column(String(20))

    contact: Mapped[Contact] = relationship(lazy="joined")


class DealMember(Base):
    """Участники сделки со стороны исполнителя."""

    __tablename__ = "deal_members"

    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str | None] = mapped_column(String(100))

    user: Mapped[User] = relationship(lazy="joined")


class DealStageHistory(Base):
    __tablename__ = "deal_stage_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), index=True)
    from_stage_id: Mapped[int | None] = mapped_column(ForeignKey("pipeline_stages.id", ondelete="SET NULL"))
    to_stage_id: Mapped[int] = mapped_column(ForeignKey("pipeline_stages.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    seconds_in_prev: Mapped[int | None] = mapped_column(Integer)
