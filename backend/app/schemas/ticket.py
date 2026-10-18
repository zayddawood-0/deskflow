import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.enums import SLAState, TicketPriority, TicketStatus
from app.schemas.common import CategoryRef, UserRef


class TicketOut(BaseModel):
    id: uuid.UUID
    ticket_number: str
    title: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    category: CategoryRef
    requester: UserRef
    assignee: UserRef | None
    auto_assigned: bool
    first_response_due_at: datetime
    resolution_due_at: datetime
    first_responded_at: datetime | None
    resolved_at: datetime | None
    paused_at: datetime | None
    total_paused_seconds: int
    sla_state: SLAState
    sla_breached: bool
    created_at: datetime
    updated_at: datetime


class TicketCreate(BaseModel):
    title: Annotated[str, Field(min_length=5, max_length=200)]
    description: Annotated[str, Field(min_length=10, max_length=20000)]
    category_id: uuid.UUID
    priority: TicketPriority = TicketPriority.MEDIUM
    auto_assign: bool = True


class TicketUpdate(BaseModel):
    title: Annotated[str, Field(min_length=5, max_length=200)] | None = None
    description: Annotated[str, Field(min_length=10, max_length=20000)] | None = None
    priority: TicketPriority | None = None
    category_id: uuid.UUID | None = None


class TicketStatusUpdate(BaseModel):
    status: TicketStatus
    note: Annotated[str, Field(max_length=1000)] | None = None


class AssignRequest(BaseModel):
    assignee_id: uuid.UUID
