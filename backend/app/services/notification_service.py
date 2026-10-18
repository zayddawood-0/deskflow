from app.models.enums import NotificationType, UserRole
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories import notification_repository


def create(
    db,
    *,
    user: User | None,
    notification_type: str,
    title: str,
    body: str | None,
    ticket: Ticket | None = None,
) -> None:
    if user is None or not user.is_active:
        return
    notification_repository.create(
        db,
        user_id=user.id,
        notification_type=notification_type,
        title=title,
        body=body,
        ticket_id=ticket.id if ticket is not None else None,
    )


def create_deduped(
    db,
    *,
    user: User | None,
    notification_type: str,
    title: str,
    body: str | None,
    ticket: Ticket,
) -> None:
    if user is None or not user.is_active:
        return
    if notification_repository.exists(
        db, user_id=user.id, notification_type=notification_type, ticket_id=ticket.id
    ):
        return
    create(
        db,
        user=user,
        notification_type=notification_type,
        title=title,
        body=body,
        ticket=ticket,
    )


def assignment_changed(
    db, *, ticket: Ticket, new_assignee: User | None, actor: User | None
) -> None:
    if new_assignee is not None and (actor is None or new_assignee.id != actor.id):
        create(
            db,
            user=new_assignee,
            notification_type=NotificationType.TICKET_ASSIGNED,
            title=f"You were assigned {ticket.ticket_number}",
            body=f"{ticket.title} · {ticket.priority.value}",
            ticket=ticket,
        )
    create(
        db,
        user=ticket.requester,
        notification_type=NotificationType.TICKET_ASSIGNED,
        title=f"{ticket.ticket_number} was assigned",
        body=f"{ticket.title} · {ticket.priority.value}",
        ticket=ticket,
    )


def unassigned(db, *, ticket: Ticket, actor: User) -> None:
    create(
        db,
        user=ticket.requester,
        notification_type=NotificationType.TICKET_ASSIGNED,
        title=f"{ticket.ticket_number} was unassigned",
        body=ticket.title,
        ticket=ticket,
    )


def comment_added(db, *, ticket: Ticket, author: User) -> None:
    recipient = ticket.assignee if author.role == UserRole.REQUESTER else ticket.requester
    if recipient is None or recipient.id == author.id:
        return
    create(
        db,
        user=recipient,
        notification_type=NotificationType.COMMENT_ADDED,
        title=f"New comment on {ticket.ticket_number}",
        body=ticket.title,
        ticket=ticket,
    )


def status_changed(db, *, ticket: Ticket, recipient: User | None, actor: User | None) -> None:
    if recipient is None or (actor is not None and recipient.id == actor.id):
        return
    create(
        db,
        user=recipient,
        notification_type=NotificationType.STATUS_CHANGED,
        title=f"{ticket.ticket_number} is now {ticket.status.value}",
        body=ticket.title,
        ticket=ticket,
    )
