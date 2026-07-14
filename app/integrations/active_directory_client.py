import logging

logger = logging.getLogger(__name__)


class ActiveDirectoryClient:
    """Stub. Produção exige autorização, conta de serviço e privilégio mínimo."""
    def _disabled(self):
        logger.warning("Tentativa de acesso à integração Active Directory desabilitada")
        raise NotImplementedError("A integração com Active Directory não está habilitada.")
    def get_user(self): return self._disabled()
    def check_account_status(self): return self._disabled()
    def check_password_expiration(self): return self._disabled()
    def check_account_locked(self): return self._disabled()
    def unlock_account(self): return self._disabled()  # Nunca liberar sem autorização e auditoria.

