import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import UserRole


class Page[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int
    pages: int


class Items[T](BaseModel):
    items: list[T]


def paginate[T](items: list[T], total: int, page: int, page_size: int) -> Page[T]:
    pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return Page(items=items, page=page, page_size=page_size, total=total, pages=pages)


class CategoryRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class UserRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    role: UserRole


class ActorRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    role: UserRole
