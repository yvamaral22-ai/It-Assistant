from app.models import SupportSession


STATUS_LABELS = {
    "in_progress": "Em andamento", "resolved": "Resolvido",
    "unresolved": "Não resolvido", "abandoned": "Abandonado",
}


def build_summary(item: SupportSession) -> str:
    triage = next(
        (interaction for interaction in item.interactions if interaction.node_type == "triage"),
        None,
    )
    lines = [
        "RESUMO DO ATENDIMENTO DE TI",
        f"ID: {item.id}",
        f"Usuário: {item.user_name or 'Não informado'}",
        f"Setor: {item.department or 'Não informado'}",
        f"Computador: {item.computer_name or 'Não informado'}",
        f"Localidade: {item.location or 'Não informada'}",
        f"Categoria: {item.category.title()}",
        f"Tipo de problema: {item.issue_type or 'Não informado'}",
        f"Problema interpretado: {triage.question_text if triage else 'Não classificado'}",
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
    if item.rating:
        lines.append(f"Avaliação do atendimento: {item.rating}/5")
    return "\n".join(lines)
