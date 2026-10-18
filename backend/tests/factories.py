import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.audit_log import AuditLog
from app.models.category import Category
from app.models.enums import TicketPriority, TicketStatus, UserRole
from app.models.ticket import Ticket
from app.models.user import User

DEFAULT_PASSWORD = "Str0ngPass"


def auth_header(user: User) -> dict[str, str]:
    token, _ = create_access_token(user_id=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


def make_user(
    db: Session,
    *,
    role: UserRole = UserRole.REQUESTER,
    email: str | None = None,
    password: str = DEFAULT_PASSWORD,
    is_active: bool = True,
    full_name: str = "Test User",
) -> User:
    user = User(
        email=email or f"{role.value}-{uuid.uuid4().hex[:8]}@test.dev",
        full_name=full_name,
        hashed_password=hash_password(password),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    return user


def make_category(db: Session, *, name: str | None = None, is_active: bool = True) -> Category:
    category = Category(
        name=name or f"Category {uuid.uuid4().hex[:8]}",
        description="Test category",
        is_active=is_active,
    )
    db.add(category)
    db.flush()
    return category


def make_ticket(
    db: Session,
    *,
    requester: User,
    category: Category,
    status: TicketStatus = TicketStatus.OPEN,
    priority: TicketPriority = TicketPriority.MEDIUM,
    assignee: User | None = None,
    title: str = "Test ticket title",
    description: str = "A description long enough for validation.",
    created_at: datetime | None = None,
    first_response_minutes: int = 480,
    resolution_minutes: int = 2880,
) -> Ticket:
    created = created_at or datetime.now(UTC)
    ticket = Ticket(
        ticket_number=f"TCK-{uuid.uuid4().int % 1_000_000}",
        title=title,
        description=description,
        status=status,
        priority=priority,
        category_id=category.id,
        requester_id=requester.id,
        assignee_id=assignee.id if assignee else None,
        first_response_due_at=created + timedelta(minutes=first_response_minutes),
        resolution_due_at=created + timedelta(minutes=resolution_minutes),
        created_at=created,
        updated_at=created,
    )
    db.add(ticket)
    db.flush()
    return ticket


def make_audit_log(
    db: Session,
    *,
    entity_id: uuid.UUID,
    ticket: Ticket | None = None,
    actor: User | None = None,
    action: str = "STATUS_CHANGED",
    entity_type: str = "ticket",
    old_value: dict | None = None,
    new_value: dict | None = None,
    created_at: datetime | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_role=actor.role if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ticket_id=ticket.id if ticket else None,
        old_value=old_value,
        new_value=new_value,
    )
    if created_at is not None:
        entry.created_at = created_at
    db.add(entry)
    db.flush()
    return entry
