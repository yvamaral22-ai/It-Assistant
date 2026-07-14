import logging

logger = logging.getLogger(__name__)


class GLPIClient:
    def __init__(self, mock: bool = False):
        self.mock = mock

    def _result(self, action: str):
        if self.mock:
            return {"mock": True, "action": action}
        logger.warning("Tentativa de acesso à integração GLPI desabilitada")
        raise NotImplementedError("A integração com GLPI não está habilitada.")
    def authenticate(self): return self._result("authenticate")
    def create_ticket(self): return self._result("create_ticket")
    def add_followup(self): return self._result("add_followup")
    def close_session(self): return self._result("close_session")
