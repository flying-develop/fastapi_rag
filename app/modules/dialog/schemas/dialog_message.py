"""Pydantic schemas (DTOs) for `DialogMessage`."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DialogMessageCreate(BaseModel):
    """Input DTO for appending a message to a dialog's history."""

    dialog_id: int
    role: Literal["user", "assistant", "system"]
    content: str


class DialogMessageRead(BaseModel):
    """Output DTO — a message as read back from the database."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    dialog_id: int
    role: str
    content: str
    created_at: datetime
