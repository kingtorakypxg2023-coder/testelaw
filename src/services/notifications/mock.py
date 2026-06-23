"""Notificador *mock* — registra em log e em memória, sem enviar nada."""
from __future__ import annotations

from src.services.notifications.base import Notifier
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MockNotifier(Notifier):
    """Simula o envio de notificações (default, sem credenciais)."""

    def __init__(self) -> None:
        self.enviadas: list[tuple[str, str]] = []

    def enviar(self, titulo: str, mensagem: str, *, urgente: bool = False) -> bool:
        self.enviadas.append((titulo, mensagem))
        logger.info("[MOCK-NOTIFY] %s%s", "[URGENTE] " if urgente else "", titulo)
        return True
