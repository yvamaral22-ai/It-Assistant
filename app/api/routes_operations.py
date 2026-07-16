from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.routes_control import csrf_token, verify_csrf
from app.config import BASE_DIR
from app.database import get_db
from app.models import User
from app.services.access_control import authorized_user, has_permission, redirect_to_login
from app.services.audit_service import AuditService
from app.services.datetime_service import format_local_datetime
from app.services.operations_service import NOTICE_SEVERITIES, OperationsService

router = APIRouter(prefix="/admin/control/notices", tags=["notices-control"])
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


def context(request: Request, db: Session, user: User, error: str | None = None) -> dict:
    service = OperationsService(db)
    return {
        "user": user,
        "notices": service.all_notices(),
        "notice_severities": NOTICE_SEVERITIES,
        "can_edit": has_permission(user, "notices.write"),
        "csrf_token": csrf_token(request),
        "error": error,
        "format_local_datetime": format_local_datetime,
    }


def editor(request: Request, db: Session) -> User:
    user = authorized_user(request, db, "notices.write")
    if not user:
        raise HTTPException(403, "Permissão para atualizar a comunicação operacional necessária.")
    return user


def audit(request: Request, db: Session, user: User, action: str, entity: str, item_id: int, details: dict) -> None:
    AuditService(db).record(
        user, action, entity, item_id, details,
        request.client.host if request.client else None,
    )


@router.get("", response_class=HTMLResponse)
def operations_page(request: Request, db: Session = Depends(get_db)):
    user = authorized_user(request, db, "notices.read")
    if not user:
        return redirect_to_login(request)
    return templates.TemplateResponse(request, "operations.html", context(request, db, user))


@router.post("")
def create_notice(
    request: Request,
    title: str = Form(..., min_length=1, max_length=160),
    message: str = Form(..., min_length=1, max_length=1200),
    severity: str = Form(..., max_length=20),
    is_active: bool = Form(False),
    csrf: str = Form(...),
    db: Session = Depends(get_db),
):
    user = editor(request, db)
    verify_csrf(request, csrf)
    try:
        item = OperationsService(db).create_notice(user, title, message, severity, is_active)
    except ValueError as exc:
        return templates.TemplateResponse(
            request, "operations.html", context(request, db, user, str(exc)), status_code=422
        )
    audit(request, db, user, "notices.created", "internal_notice", item.id, {"title": item.title})
    return RedirectResponse("/admin/control/notices?notice_created=1", status_code=303)


@router.post("/{item_id}")
def update_notice(
    request: Request,
    item_id: int,
    title: str = Form(..., min_length=1, max_length=160),
    message: str = Form(..., min_length=1, max_length=1200),
    severity: str = Form(..., max_length=20),
    is_active: bool = Form(False),
    csrf: str = Form(...),
    db: Session = Depends(get_db),
):
    user = editor(request, db)
    verify_csrf(request, csrf)
    service = OperationsService(db)
    item = service.notice(item_id)
    if not item:
        raise HTTPException(404, "Aviso não encontrado.")
    try:
        service.update_notice(item, title, message, severity, is_active)
    except ValueError as exc:
        return templates.TemplateResponse(
            request, "operations.html", context(request, db, user, str(exc)), status_code=422
        )
    audit(
        request, db, user, "notices.updated", "internal_notice", item.id,
        {"title": item.title, "severity": item.severity, "active": item.is_active},
    )
    return RedirectResponse("/admin/control/notices?notice_updated=1", status_code=303)


@router.post("/{item_id}/delete")
def delete_notice(
    request: Request,
    item_id: int,
    csrf: str = Form(...),
    db: Session = Depends(get_db),
):
    user = editor(request, db)
    verify_csrf(request, csrf)
    service = OperationsService(db)
    item = service.notice(item_id)
    if not item:
        raise HTTPException(404, "Aviso não encontrado.")
    details = {"title": item.title, "severity": item.severity, "active": item.is_active}
    service.delete_notice(item)
    audit(request, db, user, "notices.deleted", "internal_notice", item_id, details)
    return RedirectResponse("/admin/control/notices?notice_deleted=1", status_code=303)
