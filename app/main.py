import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api import routes_control, routes_diagnostics, routes_pages, routes_reports, routes_sessions, routes_users
from app.config import BASE_DIR, get_session_secret, get_settings
from app.database_migrations import run_migrations
from app.database import engine
from app.repositories.knowledge_repository import KnowledgeRepository
from sqlalchemy import text as sql_text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    settings = get_settings()
    log_dir = Path(settings.log_dir)
    if not log_dir.is_absolute():
        log_dir = BASE_DIR / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    if not any(isinstance(handler, RotatingFileHandler) for handler in root.handlers):
        file_handler = RotatingFileHandler(
            log_dir / "application.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    if not root.handlers or all(isinstance(handler, RotatingFileHandler) for handler in root.handlers):
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)


@asynccontextmanager
async def lifespan(_: FastAPI):
    (BASE_DIR / "data").mkdir(exist_ok=True)
    run_migrations()
    configure_logging()
    logger.info("Aplicação inicializada")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name, debug=settings.app_debug, lifespan=lifespan)
    application.add_middleware(
        SessionMiddleware,
        secret_key=get_session_secret(settings),
        same_site="strict",
        https_only=settings.app_env == "production",
        max_age=28_800,
    )
    application.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
    application.include_router(routes_pages.router)
    application.include_router(routes_sessions.router)
    application.include_router(routes_diagnostics.router)
    application.include_router(routes_reports.router)
    application.include_router(routes_control.router)
    application.include_router(routes_users.router)

    @application.middleware("http")
    async def maintenance_guard(request: Request, call_next):
        if settings.maintenance_mode and not request.url.path.startswith(("/admin", "/health", "/ready", "/static")):
            return HTMLResponse(
                "<main style='font-family:system-ui;max-width:700px;margin:10vh auto;padding:24px'>"
                "<h1>Manutenção programada</h1><p>O assistente está temporariamente indisponível. Tente novamente em alguns minutos.</p></main>",
                status_code=503,
            )
        return await call_next(request)

    @application.get("/health")
    def health(): return {"status": "ok", "application": settings.app_name}

    @application.get("/ready")
    def ready():
        try:
            with engine.connect() as connection:
                connection.execute(sql_text("SELECT 1"))
            categories = len(KnowledgeRepository().categories())
            return {"status": "ready", "database": "ok", "knowledge_categories": categories}
        except (OSError, ValueError, SQLAlchemyError) as exc:
            logger.error("Falha de prontidão: %s", type(exc).__name__)
            return JSONResponse(status_code=503, content={"status": "not_ready"})

    @application.exception_handler(Exception)
    async def unexpected_error(_: Request, exc: Exception):
        logger.exception("Erro interno não tratado: %s", type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": "Ocorreu um erro interno. Tente novamente."})

    return application


app = create_app()
