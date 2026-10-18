from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import AuditAction, NotificationType, SLAState, TicketStatus
from app.models.sla_policy import SlaPolicy
from app.models.ticket import Ticket

_STATE_RANK = {SLAState.ON_TRACK: 0, SLAState.AT_RISK: 1, SLAState.BREACHED: 2}


def compute_due_dates(created_at: datetime, policy: SlaPolicy) -> tuple[datetime, datetime]:
    first_response_due_at = created_at + timedelta(minutes=policy.first_response_minutes)
    resolution_due_at = created_at + timedelta(minutes=policy.resolution_minutes)
    return first_response_due_at, resolution_due_at


def frozen_seconds(ticket: Ticket, now: datetime) -> float:
    frozen = float(ticket.total_paused_seconds)
    if ticket.paused_at is not None:
        frozen += (now - ticket.paused_at).total_seconds()
    return frozen


def _base_target_seconds(due_at: datetime, created_at: datetime, total_paused: int) -> float:
    return (due_at - created_at).total_seconds() - float(total_paused)


def _worst(current: SLAState, candidate: SLAState) -> SLAState:
    return candidate if _STATE_RANK[candidate] > _STATE_RANK[current] else current


def sla_state(ticket: Ticket, now: datetime, threshold: float | None = None) -> SLAState:
    if threshold is None:
        threshold = get_settings().sla_at_risk_threshold
    elapsed = (now - ticket.created_at).total_seconds() - frozen_seconds(ticket, now)
    worst = SLAState.ON_TRACK

    fr_target = _base_target_seconds(
        ticket.first_response_due_at, ticket.created_at, ticket.total_paused_seconds
    )
    if ticket.first_responded_at is not None:
        if ticket.first_responded_at > ticket.first_response_due_at:
            worst = _worst(worst, SLAState.BREACHED)
    elif elapsed > fr_target:
        worst = _worst(worst, SLAState.BREACHED)
    elif fr_target > 0 and elapsed >= threshold * fr_target:
        worst = _worst(worst, SLAState.AT_RISK)

    rs_target = _base_target_seconds(
        ticket.resolution_due_at, ticket.created_at, ticket.total_paused_seconds
    )
    if ticket.resolved_at is not None:
        if ticket.resolved_at > ticket.resolution_due_at:
            worst = _worst(worst, SLAState.BREACHED)
    elif elapsed > rs_target:
        worst = _worst(worst, SLAState.BREACHED)
    elif rs_target > 0 and elapsed >= threshold * rs_target:
        worst = _worst(worst, SLAState.AT_RISK)

    return worst


def apply_resume(ticket: Ticket, now: datetime) -> None:
    if ticket.paused_at is None:
        return
    delta = now - ticket.paused_at
    ticket.total_paused_seconds = ticket.total_paused_seconds + int(delta.total_seconds())
    ticket.first_response_due_at = ticket.first_response_due_at + delta
    ticket.resolution_due_at = ticket.resolution_due_at + delta
    ticket.paused_at = None


def evaluate_and_persist(db: Session, ticket: Ticket, now: datetime) -> SLAState:
    from app.services import audit_service, notification_service

    state = sla_state(ticket, now)
    if state == SLAState.BREACHED and not ticket.sla_breached:
        ticket.sla_breached = True
        db.flush()
        audit_service.record(
            db,
            actor=None,
            action=AuditAction.SLA_BREACHED,
            entity_type="ticket",
            entity_id=ticket.id,
            ticket_id=ticket.id,
            old_value={"sla_breached": False},
            new_value={"sla_breached": True},
        )
        for recipient in (ticket.assignee, ticket.requester):
            notification_service.create_deduped(
                db,
                user=recipient,
                notification_type=NotificationType.SLA_BREACHED,
                title=f"{ticket.ticket_number} breached its SLA",
                body=ticket.title,
                ticket=ticket,
            )
    elif state == SLAState.AT_RISK:
        notification_service.create_deduped(
            db,
            user=ticket.assignee,
            notification_type=NotificationType.SLA_AT_RISK,
            title=f"{ticket.ticket_number} is at risk of breaching",
            body=ticket.title,
            ticket=ticket,
        )
    return state


def is_open_for_scan(status: TicketStatus) -> bool:
    return status in (
        TicketStatus.OPEN,
        TicketStatus.IN_PROGRESS,
        TicketStatus.ON_HOLD,
        TicketStatus.REOPENED,
    )
