"""Pydantic schemas (DTOs) for the `dialog` module."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DialogCreate(BaseModel):
    """Input DTO for creating a new dialog."""

    user_id: int
    title: str


class DialogUpdate(BaseModel):
    """Input DTO for updating a dialog. `title` is the only mutable field
    at this stage."""

    title: str


class DialogRead(BaseModel):
    """Output DTO — a dialog as read back from the database."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime
