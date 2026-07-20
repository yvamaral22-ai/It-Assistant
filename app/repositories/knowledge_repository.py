import json
import logging
from pathlib import Path

from app.config import BASE_DIR

logger = logging.getLogger(__name__)


class KnowledgeBaseError(ValueError):
    pass


class KnowledgeRepository:
    def __init__(self, directory: Path | None = None):
        self.directory = directory or BASE_DIR / "app" / "knowledge_base"

    def categories(self) -> list[dict]:
        try:
            data = json.loads((self.directory / "categories.json").read_text(encoding="utf-8"))
            return data["categories"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.error("Falha ao carregar catálogo de categorias: %s", type(exc).__name__)
            raise KnowledgeBaseError("A base de categorias está indisponível.") from exc

    def exists(self, category: str) -> bool:
        return any(item["slug"] == category for item in self.categories())

    def load(self, category: str) -> dict:
        if not category.replace("_", "").isalnum():
            raise KnowledgeBaseError("Categoria inválida.")
        path = self.directory / f"{category}.json"
        try:
            graph = json.loads(path.read_text(encoding="utf-8"))
            self.validate(graph)
            return graph
        except (OSError, json.JSONDecodeError, KeyError, TypeError, KnowledgeBaseError) as exc:
            logger.error("Falha ao carregar base '%s': %s", category, type(exc).__name__)
            if isinstance(exc, KnowledgeBaseError):
                raise
            raise KnowledgeBaseError("O diagnóstico desta categoria está temporariamente indisponível.") from exc

    @staticmethod
    def validate(graph: dict) -> None:
        nodes = graph.get("nodes")
        start = graph.get("start_node")
        if not isinstance(nodes, dict) or start not in nodes:
            raise KnowledgeBaseError("Nó inicial inexistente.")
        triage_targets: list[str] = []
        rules = graph.get("triage_rules", [])
        if not isinstance(rules, list):
            raise KnowledgeBaseError("As regras de interpretação devem ser uma lista.")
        rule_ids: set[str] = set()
        for rule in rules:
            if not isinstance(rule, dict):
                raise KnowledgeBaseError("Regra de interpretação inválida.")
            rule_id = rule.get("id")
            label = rule.get("label")
            target = rule.get("target_node")
            keywords = rule.get("keywords")
            if not isinstance(rule_id, str) or not rule_id or rule_id in rule_ids:
                raise KnowledgeBaseError("Identificador de interpretação inválido ou duplicado.")
            if not isinstance(label, str) or not label.strip() or len(label) > 180:
                raise KnowledgeBaseError(f"Descrição de interpretação inválida: {rule_id}")
            if target not in nodes or nodes[target].get("type") != "question":
                raise KnowledgeBaseError(f"A interpretação deve levar a uma pergunta: {rule_id}")
            if (
                not isinstance(keywords, list)
                or not keywords
                or any(not isinstance(item, str) or not item.strip() or len(item) > 120 for item in keywords)
            ):
                raise KnowledgeBaseError(f"Termos de interpretação inválidos: {rule_id}")
            rule_ids.add(rule_id)
            triage_targets.append(target)
        for node_id, node in nodes.items():
            node_type = node.get("type")
            if node_type not in {"question", "solution", "end"}:
                raise KnowledgeBaseError(f"Nó sem tipo válido: {node_id}")
            if node_type == "question":
                options = node.get("options")
                if not isinstance(options, list) or not options:
                    raise KnowledgeBaseError(f"Pergunta sem opções: {node_id}")
                for option in options:
                    if not option.get("next"):
                        raise KnowledgeBaseError(f"Opção sem destino: {node_id}")
                    if option["next"] not in nodes:
                        raise KnowledgeBaseError(f"Destino inexistente: {option['next']}")
            if node_type == "solution":
                for field in ("next", "unresolved_next"):
                    if node.get(field) and node[field] not in nodes:
                        raise KnowledgeBaseError(f"Destino inexistente: {node[field]}")
        for entrypoint in {start, *triage_targets}:
            KnowledgeRepository._check_cycles(nodes, entrypoint)

    @staticmethod
    def _check_cycles(nodes: dict, start: str) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in visiting:
                raise KnowledgeBaseError("Loop infinito detectado.")
            if node_id in visited:
                return
            visiting.add(node_id)
            node = nodes[node_id]
            targets = [o["next"] for o in node.get("options", [])]
            if node.get("next"):
                targets.append(node["next"])
            if node.get("unresolved_next"):
                targets.append(node["unresolved_next"])
            for target in targets:
                visit(target)
            visiting.remove(node_id)
            visited.add(node_id)

        visit(start)
