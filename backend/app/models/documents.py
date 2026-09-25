from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType, TimestampMixin, utcnow
from app.models.crm import Company, Contact, Deal
from app.models.user import User


class FileAttachment(Base):
    """Файлы, привязанные к сделке или компании: КП, договоры, счета, презентации."""

    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    doc_type: Mapped[str] = mapped_column(String(20), default="other")  # proposal|contract|invoice|act|presentation|other
    name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str | None] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    uploader: Mapped[User | None] = relationship(lazy="joined")


class ProposalTemplate(TimestampMixin, Base):
    __tablename__ = "proposal_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    industry_id: Mapped[int | None] = mapped_column(ForeignKey("dictionary_items.id", ondelete="SET NULL"))
    description: Mapped[str | None] = mapped_column(Text)
    intro_text: Mapped[str] = mapped_column(Text, default="")
    terms_text: Mapped[str] = mapped_column(Text, default="")
    footer_text: Mapped[str] = mapped_column(Text, default="")
    accent_color: Mapped[str] = mapped_column(String(9), default="#1c7ed6")
    default_items: Mapped[list] = mapped_column(JSONType, default=list)  # [{product_id, quantity}]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Proposal(TimestampMixin, Base):
    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255))
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), index=True)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"))
    template_id: Mapped[int | None] = mapped_column(ForeignKey("proposal_templates.id", ondelete="SET NULL"))
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="draft", index=True)  # draft|sent|viewed|approved|rejected
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    vat_rate: Mapped[int] = mapped_column(Integer, default=20)
    valid_until: Mapped[date | None] = mapped_column(Date)
    intro_text: Mapped[str] = mapped_column(Text, default="")
    terms_text: Mapped[str] = mapped_column(Text, default="")
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    tracking_token: Mapped[str] = mapped_column(String(64), unique=True)
    sent_to: Mapped[str | None] = mapped_column(String(255))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_comment: Mapped[str | None] = mapped_column(Text)

    company: Mapped[Company | None] = relationship(lazy="joined")
    contact: Mapped[Contact | None] = relationship(lazy="joined")
    deal: Mapped[Deal | None] = relationship(lazy="joined")
    owner: Mapped[User | None] = relationship(lazy="joined")
    template: Mapped[ProposalTemplate | None] = relationship(lazy="joined")
    items: Mapped[list["ProposalItem"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="ProposalItem.sort")


class ProposalItem(Base):
    __tablename__ = "proposal_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposals.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=1)
    unit: Mapped[str] = mapped_column(String(20), default="шт.")
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    sort: Mapped[int] = mapped_column(Integer, default=0)

    @property
    def total(self) -> Decimal:
        return (Decimal(self.quantity) * Decimal(self.price) * (1 - Decimal(self.discount_percent) / 100)).quantize(Decimal("0.01"))


class Invoice(TimestampMixin, Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(32), index=True)
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="SET NULL"), index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), index=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    issued_at: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    vat_rate: Mapped[int] = mapped_column(Integer, default=20)
    items: Mapped[list] = mapped_column(JSONType, default=list)  # [{name, quantity, unit, price, discount_percent}]
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(16), default="issued", index=True)  # draft|issued|partially_paid|paid|canceled
    paid_at: Mapped[date | None] = mapped_column(Date)
    comment: Mapped[str | None] = mapped_column(Text)
    exported_1c_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company | None] = relationship(lazy="joined")
    deal: Mapped[Deal | None] = relationship(lazy="joined")
    owner: Mapped[User | None] = relationship(lazy="joined")
    payments: Mapped[list["Payment"]] = relationship(cascade="all, delete-orphan", lazy="selectin",
                                                     order_by="Payment.paid_at")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    paid_at: Mapped[date] = mapped_column(Date, index=True)
    comment: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Act(TimestampMixin, Base):
    __tablename__ = "acts"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(32), index=True)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), index=True)
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="SET NULL"), index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), index=True)
    act_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    vat_rate: Mapped[int] = mapped_column(Integer, default=20)
    items: Mapped[list] = mapped_column(JSONType, default=list)
    status: Mapped[str] = mapped_column(String(10), default="draft")  # draft|sent|signed
    exported_1c_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company | None] = relationship(lazy="joined")
    invoice: Mapped[Invoice | None] = relationship(lazy="joined")


class ReportSchedule(Base):
    __tablename__ = "report_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    report: Mapped[str] = mapped_column(String(20))  # summary|funnel|managers|sources|products|receivables
    frequency: Mapped[str] = mapped_column(String(10))  # weekly|monthly
    format: Mapped[str] = mapped_column(String(4), default="pdf")  # pdf|xlsx|csv
    email: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NumberSequence(Base):
    """Счётчики номеров документов (КП, счета, акты) по годам."""

    __tablename__ = "number_sequences"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)
