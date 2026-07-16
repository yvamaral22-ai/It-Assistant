from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.routes_control import csrf_token, verify_csrf
from app.config import BASE_DIR
from app.database import get_db
from app.models import User
from app.services.access_control import authorized_user, redirect_to_login
from app.services.audit_service import AuditService
from app.services.datetime_service import format_local_datetime
from app.services.process_post_service import ProcessPostService

router = APIRouter(prefix="/admin/control/processes", tags=["process-posts-control"])
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


def master(request: Request, db: Session) -> User | None:
    return authorized_user(request, db, "processes.manage")


def context(request: Request, db: Session, user: User, error: str | None = None) -> dict:
    return {
        "user": user,
        "posts": ProcessPostService(db).all_posts(),
        "csrf_token": csrf_token(request),
        "format_local_datetime": format_local_datetime,
        "error": error,
    }


def audit(
    request: Request, db: Session, user: User, action: str,
    item_id: int, details: dict,
) -> None:
    AuditService(db).record(
        user, action, "process_post", item_id, details,
        request.client.host if request.client else None,
    )


@router.get("", response_class=HTMLResponse)
def process_posts_page(request: Request, db: Session = Depends(get_db)):
    user = master(request, db)
    if not user:
        return redirect_to_login(request)
    return templates.TemplateResponse(request, "process_posts.html", context(request, db, user))


@router.post("")
def create_process_post(
    request: Request,
    title: str = Form(..., min_length=1, max_length=180),
    content: str = Form(..., min_length=1, max_length=5000),
    display_order: int = Form(0, ge=0, le=999),
    is_active: bool = Form(False),
    csrf: str = Form(...),
    db: Session = Depends(get_db),
):
    user = master(request, db)
    if not user:
        raise HTTPException(403, "Apenas o usuário master pode gerenciar os processos.")
    verify_csrf(request, csrf)
    try:
        item = ProcessPostService(db).create(
            user, title, content, display_order, is_active
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request, "process_posts.html", context(request, db, user, str(exc)), status_code=422
        )
    audit(request, db, user, "processes.created", item.id, {"title": item.title})
    return RedirectResponse("/admin/control/processes?created=1", status_code=303)


@router.post("/{item_id}")
def update_process_post(
    request: Request,
    item_id: int,
    title: str = Form(..., min_length=1, max_length=180),
    content: str = Form(..., min_length=1, max_length=5000),
    display_order: int = Form(0, ge=0, le=999),
    is_active: bool = Form(False),
    csrf: str = Form(...),
    db: Session = Depends(get_db),
):
    user = master(request, db)
    if not user:
        raise HTTPException(403, "Apenas o usuário master pode gerenciar os processos.")
    verify_csrf(request, csrf)
    service = ProcessPostService(db)
    item = service.get(item_id)
    if not item:
        raise HTTPException(404, "Processo não encontrado.")
    try:
        service.update(item, title, content, display_order, is_active)
    except ValueError as exc:
        return templates.TemplateResponse(
            request, "process_posts.html", context(request, db, user, str(exc)), status_code=422
        )
    audit(
        request, db, user, "processes.updated", item.id,
        {"title": item.title, "active": item.is_active, "order": item.display_order},
    )
    return RedirectResponse("/admin/control/processes?updated=1", status_code=303)


@router.post("/{item_id}/delete")
def delete_process_post(
    request: Request,
    item_id: int,
    csrf: str = Form(...),
    db: Session = Depends(get_db),
):
    user = master(request, db)
    if not user:
        raise HTTPException(403, "Apenas o usuário master pode gerenciar os processos.")
    verify_csrf(request, csrf)
    service = ProcessPostService(db)
    item = service.get(item_id)
    if not item:
        raise HTTPException(404, "Processo não encontrado.")
    title = item.title
    audit(request, db, user, "processes.deleted", item.id, {"title": title})
    service.delete(item)
    return RedirectResponse("/admin/control/processes?deleted=1", status_code=303)
