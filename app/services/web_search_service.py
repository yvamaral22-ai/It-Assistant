import html
import re
import time
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlsplit
from urllib.request import Request, urlopen

from app.config import Settings
from app.models import SupportSession
from app.services.knowledge_match_service import KnowledgeMatchService, meaningful_tokens, normalize_text

MAX_KEYWORDS = 14
WEB_NODE_ID = "web_solution"
USER_AGENT = "IT-Self-Service-Assistant/1.0"
SENSITIVE_PATTERNS = (
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", re.IGNORECASE),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE),
    re.compile(r"\b[a-z]:\\\S+", re.IGNORECASE),
    re.compile(r"\b(?:pc|nb|notebook|desktop|host)[-_]?[a-z0-9-]{3,}\b", re.IGNORECASE),
)
UNSAFE_INSTRUCTION = re.compile(
    r"\b(regedit|powershell|cmd(?:\.exe)?|gpedit|bios|registro do windows|"
    r"prompt de comando|executar como administrador|desativar (?:o )?(?:antiv[ií]rus|firewall)|"
    r"baixar|download|instalar|desinstalar|formatar|redefinir|resetar)\b",
    re.IGNORECASE,
)
ACTION_WORDS = re.compile(
    r"\b(ab|acesse|clique|confirme|feche|pressione|reinicie|selecione|teste|verifique)\w*\b",
    re.IGNORECASE,
)
_SEARCH_CACHE: dict[str, tuple[float, list[dict]]] = {}


class WebSearchError(RuntimeError):
    pass


class _ReadableTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture_depth = 0
        self.ignored_depth = 0
        self.buffer: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "nav", "header", "footer", "form"}:
            self.ignored_depth += 1
        elif tag in {"li", "p"} and not self.ignored_depth:
            self.capture_depth += 1
            self.buffer = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "header", "footer", "form"} and self.ignored_depth:
            self.ignored_depth -= 1
        elif tag in {"li", "p"} and self.capture_depth:
            value = re.sub(r"\s+", " ", html.unescape(" ".join(self.buffer))).strip()
            if 25 <= len(value) <= 400:
                self.blocks.append(value)
            self.capture_depth -= 1
            self.buffer = []

    def handle_data(self, data: str) -> None:
        if self.capture_depth and not self.ignored_depth:
            self.buffer.append(data)


class _SearchResultParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_link = False
        self.url = ""
        self.text: list[str] = []
        self.results: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        href = attributes.get("href") or ""
        if tag == "a" and href.startswith("https://"):
            self.in_link = True
            self.url = href
            self.text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.in_link:
            title = re.sub(r"\s+", " ", " ".join(self.text)).strip()
            if title:
                self.results.append({"title": title[:160], "url": self.url, "description": ""})
            self.in_link = False
            self.url = ""
            self.text = []

    def handle_data(self, data: str) -> None:
        if self.in_link:
            self.text.append(data)


class WebSearchService:
    """Build a support orientation from free public web pages without paid APIs."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def orientation(self, session: SupportSession) -> dict:
        results = self._search(self._query(session))
        steps: list[str] = []
        sources: list[dict] = []
        for result in results:
            if not self._allowed_url(result["url"]):
                continue
            page_steps = self._page_steps(result["url"])
            if not page_steps:
                page_steps = self._safe_steps([result["description"]])
            if not page_steps:
                continue
            sources.append(result)
            for step in page_steps:
                if normalize_text(step) not in {normalize_text(item) for item in steps}:
                    steps.append(step)
                if len(steps) == 5:
                    break
            if len(steps) == 5 or len(sources) == 4:
                break
        if not steps or not sources:
            raise WebSearchError("Não encontrei uma orientação externa segura e verificável.")

        references = "; ".join(
            f"{item['title']} ({urlsplit(item['url']).netloc})" for item in sources
        )
        return {
            "type": "solution",
            "title": "Teste estas verificações encontradas em fontes técnicas",
            "text": "As ações abaixo foram extraídas de páginas públicas e filtradas para manter apenas verificações reversíveis e de baixo risco.",
            "steps": steps,
            "ask_if_resolved": True,
            "external_research": True,
            "knowledge_source": {
                "label": "Pesquisa web gratuita interpretada pelo assistente",
                "reference": references[:500],
            },
        }

    def _search(self, query: str) -> list[dict]:
        cache_key = normalize_text(query)
        cached = _SEARCH_CACHE.get(cache_key)
        if cached and time.monotonic() - cached[0] < self.settings.web_search_cache_seconds:
            return cached[1]
        trusted_sites = " OR ".join(
            f"site:{domain}" for domain in self.settings.web_search_allowed_domains_list
        )
        search_url = (
            "https://search.brave.com/search?source=web&spellcheck=0&q="
            f"{quote_plus(query + ' como corrigir suporte (' + trusted_sites + ')')}"
        )
        try:
            parser = _SearchResultParser()
            parser.feed(self._get(search_url, 500_000).decode("utf-8", errors="ignore"))
        except (HTTPError, URLError, OSError, TimeoutError, UnicodeError) as exc:
            raise WebSearchError("A pesquisa web gratuita está temporariamente indisponível.") from exc
        unique_results = []
        seen_urls = set()
        for result in parser.results:
            if self._allowed_url(result["url"]) and result["url"] not in seen_urls:
                unique_results.append(result)
                seen_urls.add(result["url"])
            if len(unique_results) == 10:
                break
        if unique_results:
            _SEARCH_CACHE[cache_key] = (time.monotonic(), unique_results)
        return unique_results

    def _page_steps(self, url: str) -> list[str]:
        try:
            parser = _ReadableTextParser()
            parser.feed(self._get(url, 1_500_000, enforce_allowed_host=True).decode("utf-8", errors="ignore"))
            return self._safe_steps(parser.blocks)
        except (WebSearchError, HTTPError, URLError, OSError, TimeoutError, UnicodeError):
            return []

    @staticmethod
    def _safe_steps(blocks: list[str]) -> list[str]:
        steps = []
        for block in blocks:
            value = re.sub(r"\s+", " ", block).strip(" -•\t")
            if not ACTION_WORDS.search(value) or UNSAFE_INSTRUCTION.search(value):
                continue
            if len(value) > 300:
                value = value[:297].rsplit(" ", 1)[0] + "..."
            steps.append(value)
            if len(steps) == 5:
                break
        return steps

    def _allowed_url(self, url: str) -> bool:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname:
            return False
        hostname = parsed.hostname.lower()
        return any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in self.settings.web_search_allowed_domains_list
        )

    def _get(self, url: str, max_bytes: int, enforce_allowed_host: bool = False) -> bytes:
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"})
        with urlopen(request, timeout=self.settings.web_search_timeout_seconds) as response:
            if enforce_allowed_host and not self._allowed_url(response.geturl()):
                raise WebSearchError("A fonte redirecionou para um domínio não permitido.")
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "text/xml", "application/xml", "application/rss+xml"}:
                raise WebSearchError("A fonte retornou um formato não permitido.")
            return response.read(max_bytes + 1)[:max_bytes]

    @classmethod
    def _query(cls, session: SupportSession) -> str:
        triage = KnowledgeMatchService.from_session(session)
        sources = [
            session.category, cls._redact(session.issue_type or ""),
            triage["label"] if triage else "", cls._redact(session.initial_description or ""),
        ]
        keywords: list[str] = []
        seen: set[str] = set()
        for source in sources:
            meaningful = meaningful_tokens(source)
            for token in normalize_text(source).split():
                if token not in meaningful or token in seen or len(token) < 2:
                    continue
                seen.add(token)
                keywords.append(token)
                if len(keywords) == MAX_KEYWORDS:
                    return " ".join(keywords)
        return " ".join(keywords) or "suporte tecnico"

    @staticmethod
    def _redact(value: str) -> str:
        redacted = value
        for pattern in SENSITIVE_PATTERNS:
            redacted = pattern.sub(" ", redacted)
        return redacted
