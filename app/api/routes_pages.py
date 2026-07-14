import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.database import get_db
from app.repositories.knowledge_repository import KnowledgeBaseError, KnowledgeRepository
from app.repositories.session_repository import SessionRepository
from app.services.summary_service import build_summary

router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    try: categories = KnowledgeRepository().categories()
    except KnowledgeBaseError: categories = []
    return templates.TemplateResponse(request, "index.html", {"categories": categories})


@router.get("/diagnostic/{category}", response_class=HTMLResponse)
def diagnostic_page(request: Request, category: str):
    knowledge = KnowledgeRepository()
    if not knowledge.exists(category): raise HTTPException(404, "Categoria não encontrada.")
    return templates.TemplateResponse(request, "diagnostic.html", {"category": category})


@router.get("/admin/sessions", response_class=HTMLResponse)
def admin_sessions(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "admin_sessions.html", {"sessions": SessionRepository(db).list_all()})


@router.get("/admin/sessions/{session_id}", response_class=HTMLResponse)
def admin_detail(request: Request, session_id: str, db: Session = Depends(get_db)):
    try:
        valid_session_id = str(uuid.UUID(session_id))
    except ValueError as exc:
        raise HTTPException(422, "ID de atendimento inválido.") from exc
    item = SessionRepository(db).get(valid_session_id)
    if not item: raise HTTPException(404, "Atendimento não encontrado.")
    return templates.TemplateResponse(request, "summary.html", {"session": item, "summary": build_summary(item), "admin": True})
