"""Pydantic schemas (DTOs) for the `files` module."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileCreate(BaseModel):
    """Input DTO for creating a `File` metadata row (repository layer)."""

    filename: str
    content_type: str
    size_bytes: int
    storage_key: str
    extracted_text: str | None
    parse_status: str


class FileResponse(BaseModel):
    """Output DTO — file metadata as returned by the API (API layer).

    `Response` suffix per `.ai-factory/rules/base.md`'s convention for
    API-layer schemas, distinct from the repository DTO `FileCreate`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: str
    size_bytes: int
    extracted_text: str | None
    parse_status: str
    created_at: datetime
