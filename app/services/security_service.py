import hmac
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from app.config import Settings

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def validate_security_settings(settings: Settings) -> None:
    if settings.max_request_body_bytes < 16_384:
        raise RuntimeError("MAX_REQUEST_BODY_BYTES não pode ser inferior a 16384.")
    if settings.session_max_age_seconds < 300:
        raise RuntimeError("SESSION_MAX_AGE_SECONDS não pode ser inferior a 300.")
    if not settings.allowed_hosts_list or "*" in settings.allowed_hosts_list:
        raise RuntimeError("ALLOWED_HOSTS deve listar explicitamente os endereços permitidos.")
    if settings.is_production:
        if settings.app_debug:
            raise RuntimeError("APP_DEBUG deve permanecer desativado em produção.")
        if not settings.public_base_url.lower().startswith("https://"):
            raise RuntimeError("PUBLIC_BASE_URL deve usar HTTPS em produção.")


def request_too_large(request: Request, settings: Settings) -> Response | None:
    raw_length = request.headers.get("content-length")
    if not raw_length:
        return None
    try:
        content_length = int(raw_length)
    except ValueError:
        return JSONResponse({"detail": "Cabeçalho Content-Length inválido."}, status_code=400)
    if content_length < 0:
        return JSONResponse({"detail": "Cabeçalho Content-Length inválido."}, status_code=400)
    if content_length > settings.max_request_body_bytes:
        return JSONResponse({"detail": "A requisição excede o limite permitido."}, status_code=413)
    return None


def invalid_cross_origin_request(request: Request, settings: Settings) -> bool:
    if request.method not in UNSAFE_METHODS:
        return False
    expected = (
        settings.public_base_url.rstrip("/")
        if settings.is_production
        else f"{request.url.scheme}://{request.url.netloc}"
    )
    source = request.headers.get("origin")
    if source:
        return source == "null" or not hmac.compare_digest(source.rstrip("/"), expected)
    referer = request.headers.get("referer")
    if not referer:
        return False
    parsed = urlsplit(referer)
    referer_origin = f"{parsed.scheme}://{parsed.netloc}"
    return not hmac.compare_digest(referer_origin, expected)


def add_security_headers(response: Response, request: Request, settings: Settings) -> None:
    headers = response.headers
    headers["X-Content-Type-Options"] = "nosniff"
    headers["X-Frame-Options"] = "DENY"
    headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    headers["Cross-Origin-Opener-Policy"] = "same-origin"
    headers["Cross-Origin-Resource-Policy"] = "same-origin"
    headers["X-Robots-Tag"] = "noindex, nofollow"
    headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; "
        "form-action 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'"
    )
    if request.url.path.startswith("/static/"):
        headers.setdefault("Cache-Control", "public, max-age=86400")
    else:
        headers["Cache-Control"] = "no-store"
        headers["Pragma"] = "no-cache"
    if settings.is_production:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
