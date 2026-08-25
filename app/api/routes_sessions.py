import logging
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Interaction
from app.repositories.knowledge_repository import KnowledgeBaseError
from app.repositories.session_repository import SessionRepository
from app.schemas import AnswerRequest, FeedbackRequest, FinishRequest, SessionCreate, SessionRead, SolutionResultRequest
from app.services.diagnostic_service import DiagnosticError, DiagnosticService
from app.services.summary_service import build_summary
from app.services.knowledge_match_service import KnowledgeMatchService
from app.services.web_search_service import WEB_NODE_ID, WebSearchError, WebSearchService

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)


def repository(db: Session = Depends(get_db)) -> SessionRepository:
    return SessionRepository(db)


def valid_id(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise HTTPException(422, "ID de atendimento inválido.") from exc


def get_or_404(request: Request, repo: SessionRepository, session_id: str):
    normalized_id = valid_id(session_id)
    owned_id = str(request.session.get("diagnostic_session_id", ""))
    if not owned_id or not secrets.compare_digest(owned_id, normalized_id):
        raise HTTPException(404, "Atendimento não encontrado.")
    item = repo.get(normalized_id)
    if not item:
        raise HTTPException(404, "Atendimento não encontrado.")
    return item


@router.post("", status_code=status.HTTP_201_CREATED)
def create(request: Request, payload: SessionCreate, repo: SessionRepository = Depends(repository)):
    try:
        item, node, interpretation = DiagnosticService(repo).create_session(payload)
        request.session["diagnostic_session_id"] = item.id
        return {
            "session": SessionRead.model_validate(item),
            "node": node,
            "interpretation": interpretation,
            "can_go_back": False,
        }
    except (DiagnosticError, KnowledgeBaseError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/{session_id}")
def read(request: Request, session_id: str, repo: SessionRepository = Depends(repository)):
    item = get_or_404(request, repo, session_id)
    try:
        node = DiagnosticService(repo).current_node(item)
    except (DiagnosticError, KnowledgeBaseError) as exc:
        raise HTTPException(503, str(exc)) from exc
    return {
        "session": SessionRead.model_validate(item),
        "node": node,
        "interpretation": KnowledgeMatchService.from_session(item),
        "can_go_back": repo.has_answer(item.id),
    }


@router.post("/{session_id}/answer")
def answer(
    request: Request, session_id: str, payload: AnswerRequest,
    repo: SessionRepository = Depends(repository),
):
    item = get_or_404(request, repo, session_id)
    try:
        node_id, node = DiagnosticService(repo).answer(item, payload)
        return {"node_id": node_id, "node": node, "can_go_back": True}
    except (DiagnosticError, KnowledgeBaseError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/{session_id}/continue")
def continue_flow(
    request: Request, session_id: str, repo: SessionRepository = Depends(repository),
):
    item = get_or_404(request, repo, session_id)
    try:
        node_id, node = DiagnosticService(repo).continue_after_solution(item)
        return {"node_id": node_id, "node": node, "can_go_back": repo.has_answer(item.id)}
    except (DiagnosticError, KnowledgeBaseError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/{session_id}/solution-result")
def solution_result(
    request: Request, session_id: str, payload: SolutionResultRequest,
    repo: SessionRepository = Depends(repository),
):
    item = get_or_404(request, repo, session_id)
    if item.current_node_id == WEB_NODE_ID:
        repo.mark_solution_result(item, payload.result)
        if payload.result == "not_tested":
            return {"status": "in_progress", "message": "Atendimento mantido na orientação atual."}
        repo.finish(item, payload.result, payload.feedback)
        logger.info("Sessão finalizada após pesquisa web: %s (%s)", item.id, payload.result)
        return {"status": payload.result, "summary": build_summary(repo.get(item.id))}
    if payload.result == "not_tested":
        repo.mark_solution_result(item, "not_tested")
        return {"status": "in_progress", "message": "Atendimento mantido na orientação atual."}
    if payload.result == "resolved":
        repo.mark_solution_result(item, "resolved")
        repo.finish(item, "resolved", payload.feedback)
        logger.info("Sessão finalizada: %s (resolved)", item.id)
        return {"status": "resolved", "summary": build_summary(repo.get(item.id))}
    try:
        repo.mark_solution_result(item, "unresolved")
        next_step = DiagnosticService(repo).solution_unresolved(item)
    except (DiagnosticError, KnowledgeBaseError) as exc:
        raise HTTPException(422, str(exc)) from exc
    if next_step:
        node_id, node = next_step
        return {
            "status": "in_progress",
            "node_id": node_id,
            "node": node,
            "can_go_back": repo.has_answer(item.id),
        }
    settings = get_settings()
    if settings.web_search_enabled:
        try:
            node = WebSearchService(settings).orientation(item)
        except WebSearchError as exc:
            logger.warning("Pesquisa web indisponível para a sessão %s: %s", item.id, type(exc).__name__)
            raise HTTPException(503, str(exc)) from exc
        source = node["knowledge_source"]
        displayed = "\n".join([
            node["title"], node["text"], *node["steps"],
            f"Fonte: {source['label']} ({source['reference']})",
        ])
        repo.add_interaction(Interaction(
            session_id=item.id,
            node_id=WEB_NODE_ID,
            node_type="solution",
            displayed_solution=displayed,
        ))
        repo.set_current_node(item, WEB_NODE_ID)
        return {
            "status": "in_progress",
            "node_id": WEB_NODE_ID,
            "node": node,
            "can_go_back": False,
        }
    repo.finish(item, "unresolved", payload.feedback)
    logger.info("Sessão finalizada: %s (unresolved)", item.id)
    return {"status": "unresolved", "summary": build_summary(repo.get(item.id))}


@router.post("/{session_id}/feedback")
def feedback(
    request: Request, session_id: str, payload: FeedbackRequest,
    repo: SessionRepository = Depends(repository),
):
    item = get_or_404(request, repo, session_id)
    if item.status == "in_progress":
        raise HTTPException(422, "Finalize o diagnóstico antes de avaliá-lo.")
    repo.save_feedback(item, payload.rating, payload.feedback)
    return {"rating": item.rating, "message": "Obrigado pela avaliação."}


@router.post("/{session_id}/back")
def back(request: Request, session_id: str, repo: SessionRepository = Depends(repository)):
    item = get_or_404(request, repo, session_id)
    try:
        node_id, node = DiagnosticService(repo).back(item)
        return {"node_id": node_id, "node": node, "can_go_back": repo.has_answer(item.id)}
    except (DiagnosticError, KnowledgeBaseError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/{session_id}/finish")
def finish(
    request: Request, session_id: str, payload: FinishRequest,
    repo: SessionRepository = Depends(repository),
):
    item = get_or_404(request, repo, session_id)
    if payload.status == "not_tested":
        return {"status": "in_progress", "message": "Atendimento mantido em andamento."}
    try:
        DiagnosticService(repo).validate_finish(item, payload.status)
    except (DiagnosticError, KnowledgeBaseError) as exc:
        raise HTTPException(422, str(exc)) from exc
    if payload.status in {"resolved", "unresolved"}:
        repo.mark_solution_result(item, payload.status)
    repo.finish(item, payload.status, payload.feedback)
    logger.info("Sessão finalizada: %s (%s)", item.id, payload.status)
    return {"status": item.status, "summary": build_summary(repo.get(item.id))}


@router.get("/{session_id}/summary")
def summary(request: Request, session_id: str, repo: SessionRepository = Depends(repository)):
    return {"summary": build_summary(get_or_404(request, repo, session_id))}
