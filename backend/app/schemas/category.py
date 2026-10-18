import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime


class CategoryCreate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=80)]
    description: Annotated[str, Field(max_length=2000)] | None = None


class CategoryUpdate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    description: Annotated[str, Field(max_length=2000)] | None = None
    is_active: bool | None = None
