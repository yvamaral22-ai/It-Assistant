import difflib
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import KnowledgeVersion, User
from app.repositories.knowledge_repository import KnowledgeBaseError, KnowledgeRepository
from app.services.audit_service import AuditService


class KnowledgeVersionService:
    def __init__(self, db: Session, repository: KnowledgeRepository | None = None):
        self.db = db
        self.repository = repository or KnowledgeRepository()

    def ensure_baseline(self, category: str, user: User | None = None) -> KnowledgeVersion:
        existing = self.db.scalar(
            select(KnowledgeVersion)
            .where(KnowledgeVersion.category == category)
            .order_by(KnowledgeVersion.version_number.desc())
        )
        if existing:
            return existing
        path = self._path(category)
        version = KnowledgeVersion(
            category=category,
            version_number=1,
            content=path.read_text(encoding="utf-8"),
            status="published",
            change_note="Versão inicial importada da base de conhecimento.",
            created_by=user.id if user else None,
            published_at=datetime.now(timezone.utc),
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version

    def list_versions(self, category: str) -> list[KnowledgeVersion]:
        return list(
            self.db.scalars(
                select(KnowledgeVersion)
                .where(KnowledgeVersion.category == category)
                .order_by(KnowledgeVersion.version_number.desc())
            )
        )

    def get(self, version_id: int, category: str | None = None) -> KnowledgeVersion | None:
        query = select(KnowledgeVersion).where(KnowledgeVersion.id == version_id)
        if category:
            query = query.where(KnowledgeVersion.category == category)
        return self.db.scalar(query)

    def latest_editable_content(self, category: str) -> str:
        draft = self.db.scalar(
            select(KnowledgeVersion)
            .where(KnowledgeVersion.category == category, KnowledgeVersion.status == "draft")
            .order_by(KnowledgeVersion.version_number.desc())
        )
        return draft.content if draft else self._path(category).read_text(encoding="utf-8")

    def save_draft(self, category: str, content: str, note: str | None, user: User, ip: str | None) -> KnowledgeVersion:
        normalized = self._validate(category, content)
        latest = self.db.scalar(
            select(func.max(KnowledgeVersion.version_number)).where(KnowledgeVersion.category == category)
        ) or 0
        version = KnowledgeVersion(
            category=category,
            version_number=latest + 1,
            content=normalized,
            status="draft",
            change_note=(note or "Rascunho salvo.").strip()[:500],
            created_by=user.id,
        )
        self.db.add(version)
        self.db.flush()
        AuditService(self.db).record(
            user, "knowledge.draft_created", "knowledge_version", version.id,
            {"category": category, "version": version.version_number}, ip, commit=False,
        )
        self.db.commit()
        self.db.refresh(version)
        return version

    def publish(self, version: KnowledgeVersion, user: User, ip: str | None) -> None:
        normalized = self._validate(version.category, version.content)
        path = self._path(version.category)
        backup = path.with_suffix(".json.bak")
        temporary = path.with_suffix(".json.tmp")
        current = path.read_text(encoding="utf-8")
        backup.write_text(current, encoding="utf-8")
        temporary.write_text(normalized, encoding="utf-8")
        temporary.replace(path)
        try:
            published = list(
                self.db.scalars(
                    select(KnowledgeVersion).where(
                        KnowledgeVersion.category == version.category,
                        KnowledgeVersion.status == "published",
                    )
                )
            )
            for item in published:
                item.status = "archived"
            version.status = "published"
            version.published_at = datetime.now(timezone.utc)
            AuditService(self.db).record(
                user, "knowledge.published", "knowledge_version", version.id,
                {"category": version.category, "version": version.version_number}, ip, commit=False,
            )
            self.db.commit()
        except Exception:
            path.write_text(current, encoding="utf-8")
            self.db.rollback()
            raise

    def restore_as_draft(self, version: KnowledgeVersion, user: User, ip: str | None) -> KnowledgeVersion:
        return self.save_draft(
            version.category,
            version.content,
            f"Restauração da versão {version.version_number}.",
            user,
            ip,
        )

    def diff(self, older: KnowledgeVersion, newer_content: str) -> str:
        return "\n".join(
            difflib.unified_diff(
                older.content.splitlines(), newer_content.splitlines(),
                fromfile=f"versão-{older.version_number}", tofile="conteúdo-atual", lineterm="",
            )
        )

    def _path(self, category: str) -> Path:
        if not self.repository.exists(category):
            raise KnowledgeBaseError("Categoria não encontrada.")
        return self.repository.directory / f"{category}.json"

    def _validate(self, category: str, content: str) -> str:
        if len(content.encode("utf-8")) > 200_000:
            raise KnowledgeBaseError("O arquivo excede o limite de 200 KB.")
        try:
            graph = json.loads(content)
        except json.JSONDecodeError as exc:
            raise KnowledgeBaseError(f"JSON inválido na linha {exc.lineno}, coluna {exc.colno}.") from exc
        if graph.get("category") != category:
            raise KnowledgeBaseError("A categoria interna do JSON não corresponde ao arquivo.")
        self.repository.validate(graph)
        return json.dumps(graph, ensure_ascii=False, indent=2) + "\n"
