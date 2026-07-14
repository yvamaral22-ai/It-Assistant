from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.models import User
from app.services.auth_service import AuthService

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "master": frozenset({"*"}),
    "analyst": frozenset({"control.access", "sessions.read", "reports.read", "reports.export"}),
    "editor": frozenset({"control.access", "knowledge.read", "knowledge.write"}),
    "reader": frozenset({"control.access", "sessions.read", "reports.read"}),
}


def has_permission(user: User, permission: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(user.role, frozenset())
    return "*" in permissions or permission in permissions


def authorized_user(request: Request, db: Session, permission: str) -> User | None:
    user = AuthService(db).get_active_user(request.session.get("user_id"))
    if not user or not has_permission(user, permission):
        return None
    return user


def redirect_to_login(request: Request) -> RedirectResponse | HTMLResponse:
    if request.session.get("user_id"):
        return HTMLResponse(
            "<main style='font-family:system-ui;max-width:680px;margin:10vh auto'>"
            "<h1>Acesso negado</h1><p>Seu usuário não possui a permissão necessária para esta área.</p>"
            "<a href='/admin/control'>Voltar ao painel</a></main>",
            status_code=403,
        )
    path = request.url.path
    if request.url.query:
        path = f"{path}?{request.url.query}"
    if path.startswith("/admin/") and not path.startswith("/admin/login"):
        request.session["after_login"] = path
    return RedirectResponse("/admin/login", status_code=303)
