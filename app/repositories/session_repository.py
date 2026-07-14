from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models import Interaction, SupportSession
from app.schemas import SessionCreate


class SessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: SessionCreate, start_node: str) -> SupportSession:
        item = SupportSession(**payload.model_dump(), current_node_id=start_node)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get(self, session_id: str) -> SupportSession | None:
        statement = select(SupportSession).options(selectinload(SupportSession.interactions)).where(SupportSession.id == session_id)
        return self.db.scalar(statement)

    def list_all(self) -> list[SupportSession]:
        statement = select(SupportSession).order_by(SupportSession.started_at.desc())
        return list(self.db.scalars(statement))

    def add_interaction(self, item: Interaction) -> None:
        self.db.add(item)
        self.db.commit()

    def set_current_node(self, item: SupportSession, node_id: str) -> None:
        item.current_node_id = node_id
        self.db.commit()

    def finish(self, item: SupportSession, status: str, feedback: str | None) -> None:
        item.status = status
        item.final_feedback = feedback
        item.finished_at = datetime.now(timezone.utc)
        self.db.commit()

    def rewind_last_answer(self, item: SupportSession) -> str | None:
        """Remove the last answered question and everything recorded after it."""
        interactions = list(item.interactions)
        last_question = next(
            (interaction for interaction in reversed(interactions) if interaction.node_type == "question"),
            None,
        )
        if last_question is None:
            return None
        self.db.execute(
            delete(Interaction).where(
                Interaction.session_id == item.id,
                Interaction.id >= last_question.id,
            )
        )
        item.current_node_id = last_question.node_id
        self.db.commit()
        self.db.expire(item, ["interactions"])
        return last_question.node_id
