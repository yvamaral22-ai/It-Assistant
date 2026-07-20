import re
import unicodedata
from dataclasses import dataclass

from app.models import Interaction, SupportSession

HIGH_CONFIDENCE = 0.80
MEDIUM_CONFIDENCE = 0.55
STOP_WORDS = {
    "a", "ao", "as", "com", "da", "das", "de", "do", "dos", "e", "em",
    "esta", "meu", "minha", "na", "nas", "no", "nos", "o", "os", "para",
    "por", "que", "um", "uma",
}


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", without_accents).strip()


def meaningful_tokens(value: str) -> set[str]:
    return {token for token in normalize_text(value).split() if token not in STOP_WORDS}


@dataclass(frozen=True)
class KnowledgeMatch:
    rule_id: str
    label: str
    confidence: float
    target_node: str
    default_node: str
    source: str

    @property
    def level(self) -> str:
        if self.confidence >= HIGH_CONFIDENCE:
            return "high"
        if self.confidence >= MEDIUM_CONFIDENCE:
            return "medium"
        return "low"

    @property
    def routed_node(self) -> str:
        return self.target_node if self.level == "high" else self.default_node

    def public_data(self) -> dict:
        messages = {
            "high": "Encontrei uma correspondência forte. Vou confirmar algumas informações antes de orientar.",
            "medium": "Encontrei uma possível correspondência. Preciso confirmar algumas informações.",
            "low": "Ainda preciso entender melhor o problema antes de procurar uma solução.",
        }
        return {
            "label": self.label,
            "confidence_level": self.level,
            "message": messages[self.level],
            "source": "Base de conhecimento aprovada pela TI",
        }


class KnowledgeMatchService:
    def match(self, graph: dict, description: str) -> KnowledgeMatch:
        normalized_description = normalize_text(description)
        description_tokens = meaningful_tokens(description)
        best_rule: dict | None = None
        best_score = 0.0
        for rule in graph.get("triage_rules", []):
            score = max(
                (
                    self._keyword_score(keyword, normalized_description, description_tokens)
                    for keyword in rule["keywords"]
                ),
                default=0.0,
            )
            if score > best_score:
                best_rule = rule
                best_score = score
        if best_rule:
            return KnowledgeMatch(
                rule_id=best_rule["id"],
                label=best_rule["label"],
                confidence=round(best_score, 3),
                target_node=best_rule["target_node"],
                default_node=graph["start_node"],
                source=best_rule.get("source", f"local:{graph['category']}:{best_rule['id']}"),
            )
        return KnowledgeMatch(
            rule_id="unclassified",
            label=graph["title"],
            confidence=0.0,
            target_node=graph["start_node"],
            default_node=graph["start_node"],
            source=f"local:{graph['category']}:unclassified",
        )

    @staticmethod
    def from_session(session: SupportSession) -> dict | None:
        interaction = next(
            (item for item in session.interactions if item.node_type == "triage"),
            None,
        )
        if not interaction:
            return None
        try:
            confidence = float(interaction.selected_value or 0)
        except ValueError:
            confidence = 0.0
        match = KnowledgeMatch(
            rule_id=interaction.node_id,
            label=interaction.question_text or "Problema ainda não classificado",
            confidence=confidence,
            target_node=session.current_node_id or "",
            default_node=session.current_node_id or "",
            source=interaction.selected_label or "local:unknown",
        )
        return match.public_data()

    @staticmethod
    def interaction(session_id: str, match: KnowledgeMatch) -> Interaction:
        return Interaction(
            session_id=session_id,
            node_id=match.rule_id,
            node_type="triage",
            question_text=match.label,
            selected_value=f"{match.confidence:.3f}",
            selected_label=match.source,
        )

    @staticmethod
    def _keyword_score(keyword: str, normalized_description: str, description_tokens: set[str]) -> float:
        normalized_keyword = normalize_text(keyword)
        keyword_tokens = meaningful_tokens(keyword)
        if not normalized_keyword or not keyword_tokens:
            return 0.0
        if normalized_keyword in normalized_description:
            return min(0.98, 0.86 + 0.02 * min(len(keyword_tokens), 6))
        overlap = len(keyword_tokens & description_tokens)
        if not overlap:
            return 0.0
        coverage = overlap / len(keyword_tokens)
        precision = overlap / max(len(description_tokens), 1)
        return min(0.79, 0.68 * coverage + 0.32 * min(1.0, precision * 3))
