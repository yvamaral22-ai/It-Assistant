import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import routes_diagnostics, routes_pages, routes_sessions
from app.config import BASE_DIR, get_settings
from app.database import initialize_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name, debug=settings.app_debug)
    application.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
    application.include_router(routes_pages.router)
    application.include_router(routes_sessions.router)
    application.include_router(routes_diagnostics.router)

    @application.on_event("startup")
    def startup() -> None:
        (BASE_DIR / "data").mkdir(exist_ok=True)
        initialize_database()
        logger.info("Aplicação inicializada")

    @application.get("/health")
    def health(): return {"status": "ok", "application": settings.app_name}

    @application.exception_handler(Exception)
    async def unexpected_error(_: Request, exc: Exception):
        logger.exception("Erro interno não tratado: %s", type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": "Ocorreu um erro interno. Tente novamente."})

    return application


app = create_app()

