from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import TicketPriority


class SlaPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    priority: TicketPriority
    first_response_minutes: int
    resolution_minutes: int
    updated_at: datetime


class SlaPolicyUpdate(BaseModel):
    first_response_minutes: Annotated[int, Field(ge=1, le=10080)]
    resolution_minutes: Annotated[int, Field(ge=1, le=10080)]

    @model_validator(mode="after")
    def _first_within_resolution(self) -> "SlaPolicyUpdate":
        if self.first_response_minutes > self.resolution_minutes:
            raise ValueError(
                "first_response_minutes must be less than or equal to resolution_minutes"
            )
        return self
