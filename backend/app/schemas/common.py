from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Ref(ORM):
    id: int
    name: str


class UserRef(ORM):
    id: int
    full_name: str
    email: str | None = None


class StageRef(ORM):
    id: int
    name: str
    color: str
    kind: str
    probability: int


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class Message(BaseModel):
    detail: str
