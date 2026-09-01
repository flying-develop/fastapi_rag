"""SQLAlchemy ORM model for the `dialog` module."""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base


class Dialog(Base):
    """A single dialog (chat session) between a user and the LLM.

    No `DialogMessage` yet and no foreign key to a `users` table — both
    land in the "Диалоги с LLM" milestone. This module only establishes
    the repository pattern other modules will follow.
    """

    __tablename__ = "dialogs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    title: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
