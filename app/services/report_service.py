import csv
import io
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Interaction, SupportSession


@dataclass(frozen=True)
class ReportFilters:
    date_from: date | None = None
    date_to: date | None = None
    category: str | None = None
    status: str | None = None


class ReportService:
    """Build aggregate operational reports without exposing raw answers."""

    def __init__(self, db: Session):
        self.db = db

    def _conditions(self, filters: ReportFilters) -> list:
        conditions = []
        if filters.date_from:
            conditions.append(
                SupportSession.started_at >= datetime.combine(filters.date_from, time.min, timezone.utc)
            )
        if filters.date_to:
            next_day = filters.date_to + timedelta(days=1)
            conditions.append(
                SupportSession.started_at < datetime.combine(next_day, time.min, timezone.utc)
            )
        if filters.category:
            conditions.append(SupportSession.category == filters.category)
        if filters.status:
            conditions.append(SupportSession.status == filters.status)
        return conditions

    def build(self, filters: ReportFilters) -> dict:
        conditions = self._conditions(filters)
        totals = self.db.execute(
            select(
                func.count(SupportSession.id),
                func.sum(case((SupportSession.status == "resolved", 1), else_=0)),
                func.sum(case((SupportSession.status == "unresolved", 1), else_=0)),
                func.sum(case((SupportSession.status == "in_progress", 1), else_=0)),
                func.sum(case((SupportSession.status == "abandoned", 1), else_=0)),
            ).where(*conditions)
        ).one()
        total = totals[0] or 0
        resolved = totals[1] or 0
        completed = resolved + (totals[2] or 0)
        report = {
            "totals": {
                "total": total,
                "resolved": resolved,
                "unresolved": totals[2] or 0,
                "in_progress": totals[3] or 0,
                "abandoned": totals[4] or 0,
                "resolution_rate": round(resolved * 100 / completed, 1) if completed else 0,
            },
            "categories": self._ranking(SupportSession.category, conditions),
            "people": self._ranking(SupportSession.user_name, conditions, exclude_empty=True),
            "machines": self._ranking(SupportSession.computer_name, conditions, exclude_empty=True),
            "departments": self._ranking(SupportSession.department, conditions, exclude_empty=True),
            "problems": self._problem_ranking(conditions),
            "trend": self._trend(conditions),
        }
        report["insights"] = self._insights(report)
        return report

    @staticmethod
    def _insights(report: dict) -> list[dict]:
        insights: list[dict] = []
        totals = report["totals"]
        if report["categories"]:
            top = report["categories"][0]
            share = round(top["count"] * 100 / totals["total"], 1) if totals["total"] else 0
            insights.append({
                "level": "info",
                "title": "Categoria com maior demanda",
                "text": f"{top['name'].title()} representa {share}% dos atendimentos filtrados.",
            })
        recurring_machine = next((item for item in report["machines"] if item["count"] >= 2), None)
        if recurring_machine:
            insights.append({
                "level": "warning",
                "title": "Equipamento reincidente",
                "text": f"{recurring_machine['name']} aparece em {recurring_machine['count']} atendimentos e merece análise preventiva.",
            })
        weak_category = next(
            (
                item
                for item in sorted(report["categories"], key=lambda value: value["resolution_rate"])
                if item["count"] >= 2 and item["resolution_rate"] < 60
            ),
            None,
        )
        if weak_category:
            insights.append({
                "level": "danger",
                "title": "Fluxo com baixa resolução",
                "text": f"{weak_category['name'].title()} resolve {weak_category['resolution_rate']}% dos casos; revise perguntas e orientações.",
            })
        if totals["total"] and totals["abandoned"] / totals["total"] >= 0.2:
            insights.append({
                "level": "warning",
                "title": "Abandono elevado",
                "text": "Pelo menos 20% dos diagnósticos foram abandonados. Simplifique as primeiras etapas e verifique a clareza dos textos.",
            })
        if not insights:
            insights.append({
                "level": "info",
                "title": "Base em formação",
                "text": "Registre mais atendimentos para gerar recomendações automáticas confiáveis.",
            })
        return insights

    def _ranking(self, field, conditions: list, exclude_empty: bool = False) -> list[dict]:
        normalized = func.coalesce(func.nullif(func.trim(field), ""), "Não informado")
        query = (
            select(
                normalized.label("name"),
                func.count(SupportSession.id).label("count"),
                func.sum(case((SupportSession.status == "resolved", 1), else_=0)).label("resolved"),
            )
            .where(*conditions)
            .group_by(normalized)
            .order_by(func.count(SupportSession.id).desc(), normalized)
            .limit(10)
        )
        if exclude_empty:
            query = query.where(field.is_not(None), func.trim(field) != "")
        return [self._rank_item(row.name, row.count, row.resolved or 0) for row in self.db.execute(query)]

    def _problem_ranking(self, conditions: list) -> list[dict]:
        first_answer = (
            select(Interaction.session_id, func.min(Interaction.id).label("interaction_id"))
            .where(Interaction.node_type == "question")
            .group_by(Interaction.session_id)
            .subquery()
        )
        label = (
            func.coalesce(Interaction.question_text, "Etapa inicial")
            + " — "
            + func.coalesce(Interaction.selected_label, "Sem resposta")
        )
        query = (
            select(
                label.label("name"),
                func.count(SupportSession.id).label("count"),
                func.sum(case((SupportSession.status == "resolved", 1), else_=0)).label("resolved"),
            )
            .join(first_answer, first_answer.c.session_id == SupportSession.id)
            .join(Interaction, Interaction.id == first_answer.c.interaction_id)
            .where(*conditions)
            .group_by(label)
            .order_by(func.count(SupportSession.id).desc(), label)
            .limit(10)
        )
        return [self._rank_item(row.name, row.count, row.resolved or 0) for row in self.db.execute(query)]

    def _trend(self, conditions: list) -> list[dict]:
        day = func.date(SupportSession.started_at)
        query = (
            select(day.label("day"), func.count(SupportSession.id).label("count"))
            .where(*conditions)
            .group_by(day)
            .order_by(day)
        )
        return [{"day": row.day, "count": row.count} for row in self.db.execute(query)]

    @staticmethod
    def _rank_item(name: str, count: int, resolved: int) -> dict:
        return {
            "name": name,
            "count": count,
            "resolved": resolved,
            "resolution_rate": round(resolved * 100 / count, 1) if count else 0,
        }

    def export_csv(self, filters: ReportFilters) -> str:
        sessions = list(
            self.db.scalars(
                select(SupportSession)
                .where(*self._conditions(filters))
                .order_by(SupportSession.started_at.desc())
            )
        )
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerow([
            "ID", "Usuário", "Setor", "Computador", "Categoria", "Status",
            "Problema informado", "Início", "Término",
        ])
        for item in sessions:
            writer.writerow([
                item.id, self._csv_safe(item.user_name), self._csv_safe(item.department),
                self._csv_safe(item.computer_name), item.category, item.status,
                self._csv_safe(item.initial_description), item.started_at.isoformat(),
                item.finished_at.isoformat() if item.finished_at else "",
            ])
        return "\ufeff" + output.getvalue()

    @staticmethod
    def _csv_safe(value: str | None) -> str:
        text = value or ""
        if text.startswith(("=", "+", "-", "@")):
            return "'" + text
        return text
