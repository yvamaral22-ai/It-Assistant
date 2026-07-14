import json

from sqlalchemy.orm import Session

from app.models import AuditLog, User


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        user: User,
        action: str,
        entity_type: str,
        entity_id: str | int | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
        commit: bool = True,
    ) -> AuditLog:
        entry = AuditLog(
            user_id=user.id,
            username=user.username,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=json.dumps(details, ensure_ascii=False) if details else None,
            ip_address=ip_address,
        )
        self.db.add(entry)
        if commit:
            self.db.commit()
        return entry

