from fastapi import APIRouter, HTTPException

from app.repositories.knowledge_repository import KnowledgeBaseError, KnowledgeRepository

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


@router.get("/{category}")
def diagnostic(category: str):
    try:
        graph = KnowledgeRepository().load(category)
        return {"category": graph["category"], "title": graph["title"], "start_node": graph["start_node"]}
    except KnowledgeBaseError as exc:
        raise HTTPException(404, str(exc)) from exc

