import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category


def get_by_id(db: Session, category_id: uuid.UUID) -> Category | None:
    return db.get(Category, category_id)


def get_by_name(db: Session, name: str) -> Category | None:
    return db.execute(select(Category).where(Category.name == name)).scalar_one_or_none()


def list_categories(db: Session, *, include_inactive: bool = False) -> list[Category]:
    stmt = select(Category).order_by(Category.name)
    if not include_inactive:
        stmt = stmt.where(Category.is_active.is_(True))
    return list(db.execute(stmt).scalars().all())


def create(db: Session, *, name: str, description: str | None) -> Category:
    category = Category(name=name, description=description)
    db.add(category)
    db.flush()
    return category
