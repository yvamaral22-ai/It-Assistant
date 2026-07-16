from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProcessPost, User


class ProcessPostService:
    def __init__(self, db: Session):
        self.db = db

    def public_posts(self) -> list[ProcessPost]:
        return list(self.db.scalars(
            select(ProcessPost)
            .where(ProcessPost.is_active.is_(True))
            .order_by(ProcessPost.display_order, ProcessPost.title)
        ))

    def all_posts(self) -> list[ProcessPost]:
        return list(self.db.scalars(
            select(ProcessPost).order_by(ProcessPost.display_order, ProcessPost.title)
        ))

    def get(self, item_id: int) -> ProcessPost | None:
        return self.db.get(ProcessPost, item_id)

    def create(
        self, user: User, title: str, content: str,
        display_order: int, is_active: bool,
    ) -> ProcessPost:
        item = ProcessPost(
            title=self._required(title),
            content=self._required(content),
            display_order=display_order,
            is_active=is_active,
            created_by=user.id,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update(
        self, item: ProcessPost, title: str, content: str,
        display_order: int, is_active: bool,
    ) -> ProcessPost:
        item.title = self._required(title)
        item.content = self._required(content)
        item.display_order = display_order
        item.is_active = is_active
        item.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return item

    def delete(self, item: ProcessPost) -> None:
        self.db.delete(item)
        self.db.commit()

    @staticmethod
    def _required(value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Preencha o título e as instruções do processo.")
        return normalized
