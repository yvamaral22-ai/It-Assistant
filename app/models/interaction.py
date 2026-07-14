from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.session import SupportSession


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    node_id: Mapped[str] = mapped_column(String(100))
    node_type: Mapped[str] = mapped_column(String(30))
    question_text: Mapped[str | None] = mapped_column(Text)
    selected_value: Mapped[str | None] = mapped_column(String(500))
    selected_label: Mapped[str | None] = mapped_column(String(500))
    displayed_solution: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    session: Mapped["SupportSession"] = relationship(back_populates="interactions")

