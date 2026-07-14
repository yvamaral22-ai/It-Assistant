import re

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes_control import csrf_token, verify_csrf
from app.config import BASE_DIR
from app.database import get_db
from app.models import User
from app.services.access_control import ROLE_PERMISSIONS, authorized_user, redirect_to_login
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/admin/control/users", tags=["user-management"])
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{3,80}$")


def context(request: Request, db: Session, **messages) -> dict:
    return {
        "users": AuthService(db).list_users(),
        "roles": sorted(ROLE_PERMISSIONS),
        "csrf_token": csrf_token(request),
        **messages,
    }


@router.get("", response_class=HTMLResponse)
def users_page(request: Request, db: Session = Depends(get_db)):
    if not authorized_user(request, db, "users.manage"):
        return redirect_to_login(request)
    return templates.TemplateResponse(request, "users.html", context(request, db))


@router.post("")
def create_user(
    request: Request,
    username: str = Form(..., min_length=3, max_length=80),
    password: str = Form(..., min_length=12, max_length=256),
    role: str = Form(...),
    csrf: str = Form(...),
    db: Session = Depends(get_db),
):
    actor = authorized_user(request, db, "users.manage")
    if not actor:
        raise HTTPException(403, "Permissão de gestão de usuários necessária.")
    verify_csrf(request, csrf)
    if not USERNAME_PATTERN.fullmatch(username) or role not in ROLE_PERMISSIONS:
        return templates.TemplateResponse(
            request, "users.html", context(request, db, error="Usuário ou papel inválido."), status_code=422
        )
    try:
        user = AuthService(db).create_user(username, password, role)
    except ValueError as exc:
        return templates.TemplateResponse(
            request, "users.html", context(request, db, error=str(exc)), status_code=422
        )
    AuditService(db).record(
        actor, "user.created", "user", user.id, {"username": user.username, "role": role},
        request.client.host if request.client else None,
    )
    return RedirectResponse("/admin/control/users?created=1", status_code=303)


@router.post("/{user_id}/toggle")
def toggle_user(
    request: Request, user_id: int, csrf: str = Form(...), db: Session = Depends(get_db)
):
    actor = authorized_user(request, db, "users.manage")
    if not actor:
        raise HTTPException(403, "Permissão de gestão de usuários necessária.")
    verify_csrf(request, csrf)
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "Usuário não encontrado.")
    if target.id == actor.id:
        raise HTTPException(422, "Você não pode desativar o próprio usuário.")
    if target.role == "master" and target.is_active:
        active_masters = db.scalar(
            select(func.count(User.id)).where(User.role == "master", User.is_active.is_(True))
        ) or 0
        if active_masters <= 1:
            raise HTTPException(422, "O último master ativo não pode ser desativado.")
    AuthService(db).set_active(target, not target.is_active)
    AuditService(db).record(
        actor, "user.activated" if target.is_active else "user.deactivated", "user", target.id,
        {"username": target.username}, request.client.host if request.client else None,
    )
    return RedirectResponse("/admin/control/users", status_code=303)


@router.post("/{user_id}/reset-password")
def reset_password(
    request: Request,
    user_id: int,
    password: str = Form(..., min_length=12, max_length=256),
    csrf: str = Form(...),
    db: Session = Depends(get_db),
):
    actor = authorized_user(request, db, "users.manage")
    if not actor:
        raise HTTPException(403, "Permissão de gestão de usuários necessária.")
    verify_csrf(request, csrf)
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "Usuário não encontrado.")
    AuthService(db).reset_password(target, password)
    AuditService(db).record(
        actor, "user.password_reset", "user", target.id, {"username": target.username},
        request.client.host if request.client else None,
    )
    return RedirectResponse("/admin/control/users?reset=1", status_code=303)


@router.post("/{user_id}/role")
def change_role(
    request: Request,
    user_id: int,
    role: str = Form(...),
    csrf: str = Form(...),
    db: Session = Depends(get_db),
):
    actor = authorized_user(request, db, "users.manage")
    if not actor:
        raise HTTPException(403, "Permissão de gestão de usuários necessária.")
    verify_csrf(request, csrf)
    target = db.get(User, user_id)
    if not target or role not in ROLE_PERMISSIONS:
        raise HTTPException(422, "Usuário ou papel inválido.")
    if target.id == actor.id and role != "master":
        raise HTTPException(422, "Você não pode remover o próprio papel master.")
    if target.role == "master" and role != "master":
        active_masters = db.scalar(
            select(func.count(User.id)).where(User.role == "master", User.is_active.is_(True))
        ) or 0
        if active_masters <= 1:
            raise HTTPException(422, "O último master ativo não pode perder seu papel.")
    previous = target.role
    target.role = role
    db.commit()
    AuditService(db).record(
        actor, "user.role_changed", "user", target.id,
        {"username": target.username, "from": previous, "to": role},
        request.client.host if request.client else None,
    )
    return RedirectResponse("/admin/control/users?role=1", status_code=303)
