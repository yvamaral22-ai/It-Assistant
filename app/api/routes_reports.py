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

router = APIRouter(prefix="/admin/reports", tags=["reports"])
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")
StatusFilter = Literal["in_progress", "resolved", "unresolved", "abandoned"]


def report_filters(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    category: str | None = Query(None, max_length=40),
    status: StatusFilter | None = Query(None),
) -> ReportFilters:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "A data inicial não pode ser posterior à data final.")
    categories = {item["slug"] for item in KnowledgeRepository().categories()}
    if category and category not in categories:
        raise HTTPException(422, "Categoria de relatório inválida.")
    return ReportFilters(date_from=date_from, date_to=date_to, category=category, status=status)


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
            "categories", "problems", "solutions", "people", "machines", "assets",
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
    if not authorized_user(request, db, "reports.export"):
        return redirect_to_login(request)
    content = ReportService(db).export_csv(filters)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=relatorio-atendimentos.csv"},
    )
