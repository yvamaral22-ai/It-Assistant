import logging

from app.models import Interaction, SupportSession
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.session_repository import SessionRepository
from app.schemas import AnswerRequest, SessionCreate
from app.services.knowledge_match_service import KnowledgeMatchService

logger = logging.getLogger(__name__)


class DiagnosticError(ValueError):
    pass


class DiagnosticService:
    def __init__(self, sessions: SessionRepository, knowledge: KnowledgeRepository | None = None):
        self.sessions = sessions
        self.knowledge = knowledge or KnowledgeRepository()

    def create_session(self, payload: SessionCreate) -> tuple[SupportSession, dict, dict]:
        if not self.knowledge.exists(payload.category):
            raise DiagnosticError("Categoria de diagnóstico inválida.")
        graph = self.knowledge.load(payload.category)
        description = f"{payload.issue_type}. {payload.initial_description}"
        match = KnowledgeMatchService().match(graph, description)
        session = self.sessions.create(payload, match.routed_node)
        self.sessions.add_interaction(KnowledgeMatchService.interaction(session.id, match))
        logger.info("Sessão criada: %s", session.id)
        return session, self._node_view(graph, match.routed_node), match.public_data()

    def current_node(self, session: SupportSession) -> dict:
        graph = self.knowledge.load(session.category)
        if not session.current_node_id or session.current_node_id not in graph["nodes"]:
            raise DiagnosticError("A etapa atual do diagnóstico é inválida.")
        return self._node_view(graph, session.current_node_id)

    def answer(self, session: SupportSession, payload: AnswerRequest) -> tuple[str, dict]:
        if session.status != "in_progress":
            raise DiagnosticError("Este atendimento já foi encerrado.")
        if session.current_node_id != payload.node_id:
            raise DiagnosticError("Esta pergunta não é a etapa atual do diagnóstico.")
        graph = self.knowledge.load(session.category)
        node = graph["nodes"].get(payload.node_id)
        if not node or node.get("type") != "question":
            raise DiagnosticError("A etapa informada não aceita respostas.")
        option = next((item for item in node["options"] if item["value"] == payload.value), None)
        if not option:
            raise DiagnosticError("Resposta inválida para esta pergunta.")
        next_id = option["next"]
        next_node = graph["nodes"][next_id]
        self.sessions.add_interaction(Interaction(
            session_id=session.id, node_id=payload.node_id, node_type="question",
            question_text=node.get("text"), selected_value=payload.value,
            selected_label=option.get("label"),
        ))
        if next_node["type"] == "solution":
            self.sessions.add_interaction(Interaction(
                session_id=session.id, node_id=next_id, node_type="solution",
                displayed_solution=self._solution_text(graph, next_id),
            ))
        self.sessions.set_current_node(session, next_id)
        return next_id, self._node_view(graph, next_id)

    def continue_after_solution(self, session: SupportSession) -> tuple[str, dict]:
        graph = self.knowledge.load(session.category)
        node = graph["nodes"][session.current_node_id]
        next_id = node.get("next")
        if not next_id:
            raise DiagnosticError("Esta orientação requer uma avaliação final.")
        self.sessions.set_current_node(session, next_id)
        return next_id, self._node_view(graph, next_id)

    def solution_unresolved(self, session: SupportSession) -> tuple[str, dict] | None:
        """Advance to another diagnostic attempt, or signal that options are exhausted."""
        if session.status != "in_progress":
            raise DiagnosticError("Este atendimento já foi encerrado.")
        graph = self.knowledge.load(session.category)
        node = graph["nodes"].get(session.current_node_id)
        if not node or node.get("type") != "solution":
            raise DiagnosticError("A etapa atual não é uma orientação.")
        next_id = node.get("unresolved_next")
        if not next_id:
            return None
        self.sessions.add_interaction(Interaction(
            session_id=session.id,
            node_id=next_id,
            node_type="solution",
            displayed_solution=self._solution_text(graph, next_id),
        ))
        self.sessions.set_current_node(session, next_id)
        return next_id, self._node_view(graph, next_id)

    def back(self, session: SupportSession) -> tuple[str, dict]:
        if session.status != "in_progress":
            raise DiagnosticError("Este atendimento já foi encerrado.")
        node_id = self.sessions.rewind_last_answer(session)
        if not node_id:
            raise DiagnosticError("Não há uma pergunta anterior para retornar.")
        graph = self.knowledge.load(session.category)
        return node_id, self._node_view(graph, node_id)

    def validate_finish(self, session: SupportSession, status: str) -> None:
        """Prevent API clients from bypassing the diagnostic attempts."""
        if session.status != "in_progress":
            raise DiagnosticError("Este atendimento já foi encerrado.")
        if status == "abandoned":
            return
        graph = self.knowledge.load(session.category)
        node = graph["nodes"].get(session.current_node_id)
        if not node or node.get("type") != "solution":
            raise DiagnosticError("Avalie uma orientação antes de encerrar o atendimento.")
        if status == "unresolved" and node.get("unresolved_next"):
            raise DiagnosticError("Ainda existem outras orientações seguras para testar.")

    @staticmethod
    def _node_view(graph: dict, node_id: str) -> dict:
        node = dict(graph["nodes"][node_id])
        if node.get("type") == "solution":
            source = node.get("source") or {}
            node["knowledge_source"] = {
                "label": source.get("label", "Base de conhecimento aprovada pela TI"),
                "reference": source.get(
                    "reference", f"KB-{graph['category'].upper()}-{node_id.upper()}"
                ),
            }
        return node

    @classmethod
    def _solution_text(cls, graph: dict, node_id: str) -> str:
        node = cls._node_view(graph, node_id)
        source = node["knowledge_source"]
        return "\n".join([
            node.get("title", ""),
            node.get("text", ""),
            *node.get("steps", []),
            f"Fonte: {source['label']} ({source['reference']})",
        ])
