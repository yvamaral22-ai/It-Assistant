import logging

logger = logging.getLogger(__name__)


class MicrosoftGraphClient:
    def _disabled(self):
        logger.warning("Tentativa de acesso à integração Microsoft Graph desabilitada")
        raise NotImplementedError("A integração com Microsoft Graph não está habilitada.")
    def get_user(self): return self._disabled()
    def get_licenses(self): return self._disabled()
    def get_mailbox_information(self): return self._disabled()
