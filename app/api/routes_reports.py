from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.database import get_db
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.report_service import ReportFilters, ReportService
from app.services.access_control import authorized_user, redirect_to_login
from app.services.audit_service import AuditService

router = APIRouter(prefix="/admin/reports", tags=["reports"])
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")
StatusFilter = Literal["in_progress", "resolved", "unresolved", "abandoned"]


def report_filters(
    date_from: str | None = Query(None, max_length=10),
    date_to: str | None = Query(None, max_length=10),
    category: str | None = Query(None, max_length=40),
    status: str | None = Query(None, max_length=20),
) -> ReportFilters:
    parsed_date_from = parse_optional_date(date_from, "inicial")
    parsed_date_to = parse_optional_date(date_to, "final")
    category = category.strip() if category else None
    status = status.strip() if status else None
    if parsed_date_from and parsed_date_to and parsed_date_from > parsed_date_to:
        raise HTTPException(422, "A data inicial não pode ser posterior à data final.")
    categories = {item["slug"] for item in KnowledgeRepository().categories()}
    if category and category not in categories:
        raise HTTPException(422, "Categoria de relatório inválida.")
    valid_statuses = {"in_progress", "resolved", "unresolved", "abandoned"}
    if status and status not in valid_statuses:
        raise HTTPException(422, "Status de relatório inválido.")
    return ReportFilters(
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        category=category,
        status=status,
    )


def parse_optional_date(value: str | None, label: str) -> date | None:
    if not value or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise HTTPException(422, f"A data {label} é inválida.") from exc


@router.get("", response_class=HTMLResponse)
def reports_page(
    request: Request,
    filters: ReportFilters = Depends(report_filters),
    db: Session = Depends(get_db),
):
    if not authorized_user(request, db, "reports.read"):
        return redirect_to_login(request)
    report = ReportService(db).build(filters)
    max_values = {
        key: max((item["count"] for item in report[key]), default=1)
        for key in (
            "categories", "intents", "problems", "solutions", "people", "machines",
            "departments", "locations", "issue_types", "attempts", "trend",
        )
    }
    return templates.TemplateResponse(request, "reports.html", {
        "report": report,
        "filters": filters,
        "categories": KnowledgeRepository().categories(),
        "max_values": max_values,
    })


@router.get("/export.csv")
def export_reports(
    request: Request,
    filters: ReportFilters = Depends(report_filters),
    db: Session = Depends(get_db),
):
    user = authorized_user(request, db, "reports.export")
    if not user:
        return redirect_to_login(request)
    content = ReportService(db).export_csv(filters)
    AuditService(db).record(
        user,
        "reports.exported",
        "support_session",
        details={
            "date_from": str(filters.date_from) if filters.date_from else None,
            "date_to": str(filters.date_to) if filters.date_to else None,
            "category": filters.category,
            "status": filters.status,
        },
        ip_address=request.client.host if request.client else None,
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=relatorio-atendimentos.csv"},
    )
