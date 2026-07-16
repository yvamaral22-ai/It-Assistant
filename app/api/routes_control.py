import logging
import secrets
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.config import BASE_DIR
from app.database import get_db
from app.models import AuditLog, User
from app.repositories.knowledge_repository import KnowledgeBaseError, KnowledgeRepository
from app.services.auth_service import AuthService
from app.services.access_control import ROLE_PERMISSIONS, authorized_user, has_permission, redirect_to_login
from app.services.audit_service import AuditService
from app.services.knowledge_version_service import KnowledgeVersionService

router = APIRouter(prefix="/admin", tags=["master-control"])
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")
logger = logging.getLogger(__name__)


class LoginLimiter:
    """Small in-memory limiter for local login brute-force protection."""

    def __init__(self, attempts: int = 5, window_seconds: int = 300):
        self.attempts = attempts
        self.window_seconds = window_seconds
        self._entries: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allowed(self, client: str) -> bool:
        now = time.monotonic()
        with self._lock:
            entries = self._entries[client]
            while entries and now - entries[0] > self.window_seconds:
                entries.popleft()
            return len(entries) < self.attempts

    def failed(self, client: str) -> None:
        with self._lock:
            self._entries[client].append(time.monotonic())

    def clear(self, client: str) -> None:
        with self._lock:
            self._entries.pop(client, None)


limiter = LoginLimiter()


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def verify_csrf(request: Request, received: str) -> None:
    expected = request.session.get("csrf_token", "")
    if not expected or not secrets.compare_digest(expected, received):
        raise HTTPException(403, "A sessão do formulário expirou. Atualize a página e tente novamente.")


def active_master(request: Request, db: Session) -> User | None:
    return AuthService(db).get_active_master(request.session.get("user_id"))


def login_context(request: Request, error: str | None = None) -> dict:
    return {"csrf_token": csrf_token(request), "error": error}


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    if AuthService(db).get_active_user(request.session.get("user_id")):
        return RedirectResponse("/admin/control", status_code=303)
    return templates.TemplateResponse(request, "login.html", login_context(request))


@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    username: str = Form(..., min_length=1, max_length=80),
    password: str = Form(..., min_length=1, max_length=256),
    csrf: str = Form(...),
    db: Session = Depends(get_db),
):
    verify_csrf(request, csrf)
    client = request.client.host if request.client else "unknown"
    if not limiter.allowed(client):
        return templates.TemplateResponse(
            request, "login.html", login_context(request, "Muitas tentativas. Aguarde cinco minutos."), status_code=429
        )
    user = AuthService(db).authenticate(username, password)
    if not user or user.role not in ROLE_PERMISSIONS:
        limiter.failed(client)
        logger.warning("Falha de autenticação do painel master")
        return templates.TemplateResponse(
            request, "login.html", login_context(request, "Usuário ou senha inválidos."), status_code=401
        )
    limiter.clear(client)
    AuditService(db).record(
        user, "auth.login", "user", user.id, {"role": user.role}, client
    )
    destination = request.session.get("after_login", "/admin/control")
    if not isinstance(destination, str) or not destination.startswith("/admin/"):
        destination = "/admin/control"
    request.session.clear()
    request.session.update({"user_id": user.id, "role": user.role, "csrf_token": secrets.token_urlsafe(32)})
    return RedirectResponse(destination, status_code=303)


@router.post("/logout")
def logout(request: Request, csrf: str = Form(...), db: Session = Depends(get_db)):
    verify_csrf(request, csrf)
    user = AuthService(db).get_active_user(request.session.get("user_id"))
    if user:
        AuditService(db).record(
            user, "auth.logout", "user", user.id, ip_address=request.client.host if request.client else None
        )
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@router.get("/control", response_class=HTMLResponse)
def control_panel(request: Request, db: Session = Depends(get_db)):
    user = authorized_user(request, db, "control.access")
    if not user:
        return redirect_to_login(request)
    return templates.TemplateResponse(request, "control.html", {
        "user": user,
        "categories": KnowledgeRepository().categories(),
        "csrf_token": csrf_token(request),
        "can_edit": has_permission(user, "knowledge.write"),
        "can_manage_notices": has_permission(user, "notices.read"),
        "can_manage_processes": has_permission(user, "processes.manage"),
        "can_manage_users": has_permission(user, "users.manage"),
    })


def editor_context(request: Request, user: User, category: str, content: str, versions: list, **messages) -> dict:
    return {
        "user": user,
        "category": category,
        "content": content,
        "csrf_token": csrf_token(request),
        "versions": versions,
        **messages,
    }


@router.get("/control/knowledge/{category}", response_class=HTMLResponse)
def knowledge_editor(request: Request, category: str, db: Session = Depends(get_db)):
    user = authorized_user(request, db, "knowledge.read")
    if not user:
        return redirect_to_login(request)
    repository = KnowledgeRepository()
    if not repository.exists(category):
        raise HTTPException(404, "Categoria não encontrada.")
    service = KnowledgeVersionService(db, repository)
    service.ensure_baseline(category, user)
    return templates.TemplateResponse(
        request, "knowledge_editor.html", editor_context(
            request, user, category, service.latest_editable_content(category), service.list_versions(category),
            can_edit=has_permission(user, "knowledge.write"),
        )
    )


@router.post("/control/knowledge/{category}", response_class=HTMLResponse)
def save_knowledge(
    request: Request,
    category: str,
    content: str = Form(...),
    change_note: str = Form("", max_length=500),
    csrf: str = Form(...),
    db: Session = Depends(get_db),
):
    user = authorized_user(request, db, "knowledge.write")
    if not user:
        raise HTTPException(401, "Autenticação master necessária.")
    verify_csrf(request, csrf)
    repository = KnowledgeRepository()
    if not repository.exists(category):
        raise HTTPException(404, "Categoria não encontrada.")
    try:
        service = KnowledgeVersionService(db, repository)
        service.ensure_baseline(category, user)
        version = service.save_draft(
            category, content, change_note, user, request.client.host if request.client else None
        )
    except KnowledgeBaseError as exc:
        service = KnowledgeVersionService(db, repository)
        return templates.TemplateResponse(
            request,
            "knowledge_editor.html",
            editor_context(
                request, user, category, content, service.list_versions(category),
                error=f"Rascunho rejeitado: {exc}", can_edit=True,
            ),
            status_code=422,
        )
    logger.info("Rascunho da base de conhecimento criado: %s v%s", category, version.version_number)
    return templates.TemplateResponse(
        request,
        "knowledge_editor.html",
        editor_context(
            request, user, category, version.content, service.list_versions(category),
            success=f"Rascunho v{version.version_number} validado e salvo. Publique quando estiver pronto.",
            can_edit=True,
        ),
    )


@router.post("/control/knowledge/{category}/publish/{version_id}")
def publish_knowledge(
    request: Request, category: str, version_id: int, csrf: str = Form(...), db: Session = Depends(get_db)
):
    user = authorized_user(request, db, "knowledge.write")
    if not user:
        raise HTTPException(403, "Permissão de edição necessária.")
    verify_csrf(request, csrf)
    service = KnowledgeVersionService(db)
    version = service.get(version_id, category)
    if not version or version.status != "draft":
        raise HTTPException(404, "Rascunho não encontrado.")
    service.publish(version, user, request.client.host if request.client else None)
    return RedirectResponse(f"/admin/control/knowledge/{category}?published={version.version_number}", status_code=303)


@router.post("/control/knowledge/{category}/restore/{version_id}")
def restore_knowledge(
    request: Request, category: str, version_id: int, csrf: str = Form(...), db: Session = Depends(get_db)
):
    user = authorized_user(request, db, "knowledge.write")
    if not user:
        raise HTTPException(403, "Permissão de edição necessária.")
    verify_csrf(request, csrf)
    service = KnowledgeVersionService(db)
    version = service.get(version_id, category)
    if not version:
        raise HTTPException(404, "Versão não encontrada.")
    draft = service.restore_as_draft(version, user, request.client.host if request.client else None)
    return RedirectResponse(f"/admin/control/knowledge/{category}?restored={draft.version_number}", status_code=303)


@router.get("/control/knowledge/{category}/compare/{version_id}", response_class=HTMLResponse)
def compare_knowledge(request: Request, category: str, version_id: int, db: Session = Depends(get_db)):
    user = authorized_user(request, db, "knowledge.read")
    if not user:
        return redirect_to_login(request)
    service = KnowledgeVersionService(db)
    version = service.get(version_id, category)
    if not version:
        raise HTTPException(404, "Versão não encontrada.")
    current = service.latest_editable_content(category)
    return templates.TemplateResponse(request, "knowledge_diff.html", {
        "category": category,
        "version": version,
        "diff": service.diff(version, current) or "Não há diferenças.",
    })


@router.get("/control/audit", response_class=HTMLResponse)
def audit_page(request: Request, db: Session = Depends(get_db)):
    if not authorized_user(request, db, "audit.read"):
        return redirect_to_login(request)
    entries = list(db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(500)))
    return templates.TemplateResponse(request, "audit.html", {"entries": entries})


@router.post("/control/password", response_class=HTMLResponse)
def change_password(
    request: Request,
    current_password: str = Form(..., max_length=256),
    new_password: str = Form(..., min_length=12, max_length=256),
    confirmation: str = Form(..., max_length=256),
    csrf: str = Form(...),
    db: Session = Depends(get_db),
):
    user = AuthService(db).get_active_user(request.session.get("user_id"))
    if not user:
        raise HTTPException(401, "Autenticação master necessária.")
    verify_csrf(request, csrf)
    message: dict[str, str]
    if new_password != confirmation:
        message = {"password_error": "A confirmação não corresponde à nova senha."}
    elif not AuthService(db).change_password(user, current_password, new_password):
        message = {"password_error": "A senha atual está incorreta."}
    else:
        message = {"password_success": "Senha alterada com sucesso."}
        AuditService(db).record(
            user, "user.password_changed", "user", user.id,
            ip_address=request.client.host if request.client else None,
        )
    return templates.TemplateResponse(request, "control.html", {
        "user": user,
        "categories": KnowledgeRepository().categories(),
        "csrf_token": csrf_token(request),
        "can_edit": has_permission(user, "knowledge.write"),
        "can_manage_notices": has_permission(user, "notices.read"),
        "can_manage_processes": has_permission(user, "processes.manage"),
        "can_manage_users": has_permission(user, "users.manage"),
        **message,
    })
