import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.database import get_db
from app.repositories.knowledge_repository import KnowledgeBaseError, KnowledgeRepository
from app.repositories.session_repository import SessionRepository
from app.services.summary_service import build_summary
from app.services.access_control import authorized_user, redirect_to_login
from app.services.audit_service import AuditService
from app.services.operations_service import NOTICE_SEVERITIES, OperationsService
from app.services.process_post_service import ProcessPostService

router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    try:
        categories = KnowledgeRepository().categories()
    except KnowledgeBaseError:
        categories = []
    operations = OperationsService(db)
    return templates.TemplateResponse(request, "index.html", {
        "categories": categories,
        "notices": operations.public_notices(),
        "notice_severities": NOTICE_SEVERITIES,
        "process_posts": ProcessPostService(db).public_posts(),
    })


@router.get("/diagnostic/{category}", response_class=HTMLResponse)
def diagnostic_page(request: Request, category: str):
    knowledge = KnowledgeRepository()
    if not knowledge.exists(category):
        raise HTTPException(404, "Categoria não encontrada.")
    return templates.TemplateResponse(request, "diagnostic.html", {"category": category})


@router.get("/admin/sessions", response_class=HTMLResponse)
def admin_sessions(
    request: Request,
    page: int = Query(1, ge=1),
    query: str | None = Query(None, max_length=120),
    status: str | None = Query(None, pattern="^(in_progress|resolved|unresolved|abandoned)$"),
    category: str | None = Query(None, max_length=40),
    db: Session = Depends(get_db),
):
    if not authorized_user(request, db, "sessions.read"):
        return redirect_to_login(request)
    categories = KnowledgeRepository().categories()
    valid_categories = {item["slug"] for item in categories}
    if category and category not in valid_categories:
        raise HTTPException(422, "Categoria inválida.")
    sessions, total = SessionRepository(db).search(page, 25, query, status, category)
    return templates.TemplateResponse(request, "admin_sessions.html", {
        "sessions": sessions, "total": total, "page": page, "pages": max(1, (total + 24) // 25),
        "query": query or "", "selected_status": status or "", "selected_category": category or "",
        "categories": categories,
    })


@router.get("/admin/sessions/{session_id}", response_class=HTMLResponse)
def admin_detail(request: Request, session_id: str, db: Session = Depends(get_db)):
    user = authorized_user(request, db, "sessions.read")
    if not user:
        return redirect_to_login(request)
    try:
        valid_session_id = str(uuid.UUID(session_id))
    except ValueError as exc:
        raise HTTPException(422, "ID de atendimento inválido.") from exc
    item = SessionRepository(db).get(valid_session_id)
    if not item:
        raise HTTPException(404, "Atendimento não encontrado.")
    AuditService(db).record(
        user,
        "sessions.viewed",
        "support_session",
        item.id,
        ip_address=request.client.host if request.client else None,
    )
    return templates.TemplateResponse(request, "summary.html", {"session": item, "summary": build_summary(item), "admin": True})
