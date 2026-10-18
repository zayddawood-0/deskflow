import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.user import User

_SORT_FIELDS = {
    "full_name": User.full_name,
    "email": User.email,
    "created_at": User.created_at,
    "updated_at": User.updated_at,
}


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()


def email_exists(db: Session, email: str) -> bool:
    return get_by_email(db, email) is not None


def list_users(
    db: Session,
    *,
    role: UserRole | None = None,
    is_active: bool | None = None,
    q: str | None = None,
    sort: str = "-created_at",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[User], int]:
    conditions = []
    if role is not None:
        conditions.append(User.role == role)
    if is_active is not None:
        conditions.append(User.is_active.is_(is_active))
    if q:
        pattern = f"%{q}%"
        conditions.append(or_(User.email.ilike(pattern), User.full_name.ilike(pattern)))

    total = db.execute(select(func.count()).select_from(User).where(*conditions)).scalar_one()

    descending = sort.startswith("-")
    column = _SORT_FIELDS.get(sort.lstrip("-"), User.created_at)
    stmt = (
        select(User)
        .where(*conditions)
        .order_by(column.desc() if descending else column.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.execute(stmt).scalars().all()), total


def list_active_assignables(db: Session) -> list[User]:
    stmt = (
        select(User)
        .where(
            User.is_active.is_(True),
            User.role.in_([UserRole.AGENT, UserRole.ADMIN]),
        )
        .order_by(User.created_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def create(
    db: Session,
    *,
    email: str,
    full_name: str,
    hashed_password: str,
    role: UserRole,
) -> User:
    user = User(
        email=email.lower(),
        full_name=full_name,
        hashed_password=hashed_password,
        role=role,
    )
    db.add(user)
    db.flush()
    return user
