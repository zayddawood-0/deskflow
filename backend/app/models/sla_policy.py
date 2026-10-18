from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import TicketPriority


def utcnow() -> datetime:
    return datetime.now(UTC)


class SlaPolicy(Base):
    __tablename__ = "sla_policies"

    priority: Mapped[TicketPriority] = mapped_column(
        SAEnum(
            TicketPriority, name="ticket_priority", values_callable=lambda x: [e.value for e in x]
        ),
        primary_key=True,
    )
    first_response_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=text("now()"),
    )
