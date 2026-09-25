from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORM, UserRef

TaskType = Literal["call", "meeting", "email", "proposal", "other"]
Priority = Literal["low", "medium", "high"]


class TaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    type: TaskType = "call"
    priority: Priority = "medium"
    description: str | None = None
    assignee_id: int | None = None
    due_at: datetime
    duration_minutes: int = Field(default=30, ge=5, le=24 * 60)
    deal_id: int | None = None
    company_id: int | None = None
    contact_id: int | None = None
    lead_id: int | None = None
    reminder_minutes: Literal[15, 60, 1440] | None = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(TaskBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    type: TaskType | None = None
    priority: Priority | None = None
    due_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=24 * 60)
    status: Literal["open", "done", "canceled"] | None = None


class TaskComplete(BaseModel):
    result: str | None = None


class RelatedRef(BaseModel):
    type: str
    id: int
    name: str


class TaskOut(ORM):
    id: int
    title: str
    type: str
    priority: str
    status: str
    description: str | None
    result: str | None
    assignee: UserRef | None
    author_id: int | None
    due_at: datetime
    duration_minutes: int
    deal_id: int | None
    company_id: int | None
    contact_id: int | None
    lead_id: int | None
    reminder_minutes: int | None
    completed_at: datetime | None
    created_at: datetime
    related: list[RelatedRef] = []
    is_overdue: bool = False


class ActivityOut(ORM):
    id: int
    type: str
    title: str
    body: str | None
    user: UserRef | None
    object_type: str
    object_id: int
    company_id: int | None
    contact_id: int | None
    deal_id: int | None
    lead_id: int | None
    meta: dict
    occurred_at: datetime


class ActivityCreate(BaseModel):
    """Ручная фиксация: заметка, звонок, встреча."""
    type: Literal["note", "call", "meeting"] = "note"
    title: str | None = None
    body: str = Field(min_length=1)
    company_id: int | None = None
    contact_id: int | None = None
    deal_id: int | None = None
    lead_id: int | None = None
    occurred_at: datetime | None = None
    duration_minutes: int | None = None
    direction: Literal["in", "out"] | None = None


class EmailSendIn(BaseModel):
    to: EmailStr
    subject: str = Field(min_length=1, max_length=512)
    body: str = Field(min_length=1)
    company_id: int | None = None
    contact_id: int | None = None
    deal_id: int | None = None
    lead_id: int | None = None
    file_ids: list[int] = []


class EmailOut(ORM):
    id: int
    direction: str
    status: str
    subject: str
    body: str | None
    from_email: str | None
    to_email: str
    opened_at: datetime | None
    open_count: int
    sent_at: datetime | None
    created_at: datetime


class AuditOut(ORM):
    id: int
    user: UserRef | None
    action: str
    entity: str | None
    entity_id: int | None
    summary: str
    changes: dict | None
    ip: str | None
    created_at: datetime


class CallIn(BaseModel):
    phone: str = Field(min_length=3, max_length=50)
    contact_id: int | None = None
    company_id: int | None = None
    deal_id: int | None = None
    lead_id: int | None = None


class TelephonyEvent(BaseModel):
    event: Literal["incoming", "answered", "completed", "missed"]
    call_id: str
    direction: Literal["in", "out"] = "in"
    phone: str
    extension: str | None = None
    duration: int | None = None
    recording_url: str | None = None
    started_at: datetime | None = None
