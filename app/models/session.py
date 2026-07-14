import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SupportSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_name: Mapped[str | None] = mapped_column(String(120))
    department: Mapped[str | None] = mapped_column(String(120))
    computer_name: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(30), default="in_progress", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    initial_description: Mapped[str | None] = mapped_column(Text)
    final_feedback: Mapped[str | None] = mapped_column(Text)
    current_node_id: Mapped[str | None] = mapped_column(String(100))
    interactions: Mapped[list["Interaction"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Interaction.created_at"
    )

