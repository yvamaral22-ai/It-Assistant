from datetime import datetime, timezone

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Interaction, SupportSession
from app.schemas import SessionCreate


class SessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: SessionCreate, start_node: str) -> SupportSession:
        values = payload.model_dump()
        for field in (
            "user_name", "department", "computer_name", "location", "asset_tag",
            "device_model", "issue_type", "initial_description",
        ):
            value = values.get(field)
            values[field] = value.strip() if isinstance(value, str) and value.strip() else None
        if values.get("computer_name"):
            values["computer_name"] = values["computer_name"].upper()
        if values.get("asset_tag"):
            values["asset_tag"] = values["asset_tag"].upper()
        values["issue_type"] = values.get("issue_type") or payload.category.title()
        item = SupportSession(**values, current_node_id=start_node)
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

    def search(
        self, page: int = 1, page_size: int = 25, query: str | None = None,
        status: str | None = None, category: str | None = None,
    ) -> tuple[list[SupportSession], int]:
        conditions = []
        if query:
            pattern = f"%{query.strip()}%"
            conditions.append(or_(
                SupportSession.id.ilike(pattern), SupportSession.user_name.ilike(pattern),
                SupportSession.computer_name.ilike(pattern), SupportSession.asset_tag.ilike(pattern),
                SupportSession.initial_description.ilike(pattern),
            ))
        if status:
            conditions.append(SupportSession.status == status)
        if category:
            conditions.append(SupportSession.category == category)
        total = self.db.scalar(select(func.count(SupportSession.id)).where(*conditions)) or 0
        statement = (
            select(SupportSession).where(*conditions).order_by(SupportSession.started_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )
        return list(self.db.scalars(statement)), total

    def has_answer(self, session_id: str) -> bool:
        count = self.db.scalar(
            select(func.count(Interaction.id)).where(
                Interaction.session_id == session_id,
                Interaction.node_type == "question",
            )
        )
        return bool(count)

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

    def mark_solution_result(self, item: SupportSession, result: str) -> None:
        interaction = self.db.scalar(
            select(Interaction)
            .where(
                Interaction.session_id == item.id,
                Interaction.node_type == "solution",
                Interaction.node_id == item.current_node_id,
            )
            .order_by(Interaction.id.desc())
        )
        if interaction:
            interaction.solution_result = result
            interaction.result_at = datetime.now(timezone.utc)
            self.db.commit()

    def save_feedback(self, item: SupportSession, rating: int, feedback: str | None) -> None:
        item.rating = rating
        if feedback:
            item.final_feedback = feedback
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
