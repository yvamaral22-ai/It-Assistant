from app.models import SupportSession


STATUS_LABELS = {
    "in_progress": "Em andamento", "resolved": "Resolvido",
    "unresolved": "Não resolvido", "abandoned": "Abandonado",
}


def build_summary(item: SupportSession) -> str:
    lines = [
        "RESUMO DO ATENDIMENTO DE TI",
        f"ID: {item.id}",
        f"Usuário: {item.user_name or 'Não informado'}",
        f"Setor: {item.department or 'Não informado'}",
        f"Computador: {item.computer_name or 'Não informado'}",
        f"Categoria: {item.category.title()}",
        f"Problema informado: {item.initial_description or 'Não informado'}",
        f"Início: {item.started_at.isoformat()}",
        f"Término: {item.finished_at.isoformat() if item.finished_at else 'Em andamento'}",
        f"Resultado: {STATUS_LABELS.get(item.status, item.status)}",
        "", "DIAGNÓSTICO:",
    ]
    for interaction in item.interactions:
        if interaction.node_type == "question":
            lines.append(f"- {interaction.question_text}: {interaction.selected_label}")
        elif interaction.displayed_solution:
            lines.extend(["", "ORIENTAÇÃO APRESENTADA:", interaction.displayed_solution])
    if item.final_feedback:
        lines.extend(["", f"Observação final: {item.final_feedback}"])
    return "\n".join(lines)

