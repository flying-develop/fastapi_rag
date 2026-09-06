"""SQLAlchemy ORM model for the `files` module."""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base


class File(Base):
    """Metadata for a file uploaded through the API and stored in S3.

    The uploaded bytes themselves live in the configured S3 bucket under
    `storage_key`, not in Postgres — this row is only the metadata index.
    `storage_key` is a generated identifier, deliberately not derived from
    the client-supplied `filename` (path traversal / collision risk if it
    were), so `filename` is display-only.
    """

    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str]
    content_type: Mapped[str]
    size_bytes: Mapped[int]
    storage_key: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
