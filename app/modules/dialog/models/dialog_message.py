"""SQLAlchemy ORM model for messages within a `dialog`."""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base


class DialogMessage(Base):
    """A single message in a `Dialog`'s history.

    `role` is one of `"user"` / `"assistant"` / `"system"` — validated at
    the schema layer (`DialogMessageCreate`, Task 2), not enforced as a DB
    constraint at this stage. No ORM `relationship()` to `Dialog` — this
    module accesses the DB only through its repositories, same as `Dialog`.

    `dialog_id` FK cascades on delete — deleting a `Dialog` deletes its
    message history with it (found via /aif-review: without this,
    `DialogRepository.delete()` on a dialog with messages raised an
    unhandled `IntegrityError`).
    """

    __tablename__ = "dialog_messages"
    __table_args__ = (
        # `list_by_dialog` filters by dialog_id and sorts by created_at —
        # Postgres does not auto-index FK columns, so without this every
        # call is a full table scan once history grows.
        Index("ix_dialog_messages_dialog_id_created_at", "dialog_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dialog_id: Mapped[int] = mapped_column(
        ForeignKey("dialogs.id", ondelete="CASCADE")
    )
    role: Mapped[str]
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
