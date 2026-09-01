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


class DialogMessageCreateRequest(BaseModel):
    """API request body for `POST /dialogs/{dialog_id}/messages`.

    Only `content` — `role` is never client-supplied: the service always
    stores incoming API messages as `"user"`, so a client can't forge a
    fake `"assistant"`/`"system"` message into the history.
    """

    content: str


class DialogMessageResponse(DialogMessageRead):
    """API response body — the assistant's reply to the sent message.

    Same shape as `DialogMessageRead`; a distinct, API-facing name per
    the `Request`/`Response` suffix convention in `.ai-factory/rules/base.md`
    (which applies to the API layer — `DialogMessageCreate`/`DialogMessageRead`
    stay the internal repository DTOs).
    """
