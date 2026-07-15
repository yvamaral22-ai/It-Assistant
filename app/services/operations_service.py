from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InternalNotice, User

NOTICE_SEVERITIES = {
    "info": "Informativo",
    "warning": "Atenção",
    "critical": "Crítico",
}


class OperationsService:
    def __init__(self, db: Session):
        self.db = db

    def public_notices(self) -> list[InternalNotice]:
        return list(self.db.scalars(
            select(InternalNotice)
            .where(InternalNotice.is_active.is_(True))
            .order_by(InternalNotice.updated_at.desc(), InternalNotice.id.desc())
        ))

    def all_notices(self) -> list[InternalNotice]:
        return list(self.db.scalars(
            select(InternalNotice).order_by(InternalNotice.updated_at.desc(), InternalNotice.id.desc())
        ))

    def create_notice(
        self, user: User, title: str, message: str, severity: str, is_active: bool,
    ) -> InternalNotice:
        self._validate_notice_severity(severity)
        item = InternalNotice(
            title=self._required(title),
            message=self._required(message),
            severity=severity,
            is_active=is_active,
            created_by=user.id,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_notice(
        self, item: InternalNotice, title: str, message: str,
        severity: str, is_active: bool,
    ) -> InternalNotice:
        self._validate_notice_severity(severity)
        item.title = self._required(title)
        item.message = self._required(message)
        item.severity = severity
        item.is_active = is_active
        item.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return item

    def notice(self, item_id: int) -> InternalNotice | None:
        return self.db.get(InternalNotice, item_id)

    @staticmethod
    def _required(value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Preencha todos os campos obrigatórios.")
        return normalized

    @staticmethod
    def _validate_notice_severity(severity: str) -> None:
        if severity not in NOTICE_SEVERITIES:
            raise ValueError("Tipo de aviso inválido.")
