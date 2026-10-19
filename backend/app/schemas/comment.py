import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ActorRef


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    author: ActorRef
    body: str
    is_public: bool
    created_at: datetime


class CommentCreate(BaseModel):
    body: Annotated[str, Field(min_length=1, max_length=5000)]
    is_public: bool = True


class AuditOut(BaseModel):
    id: uuid.UUID
    actor: ActorRef | None
    action: str
    entity_type: str
    entity_id: uuid.UUID
    ticket_id: uuid.UUID | None
    old_value: dict | None
    new_value: dict | None
    created_at: datetime
