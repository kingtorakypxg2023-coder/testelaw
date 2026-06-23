"""Fábrica de notificadores."""
from __future__ import annotations

from src.config.settings import settings
from src.services.notifications.base import Notifier
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_notifier(nome: str | None = None) -> Notifier:
    """Retorna a instância do notificador solicitado."""
    nome = (nome or settings.notifier).strip().lower()
    logger.debug("Selecionando notificador: %s", nome)

    if nome in ("mock", "fake", "stub", "log", "none"):
        from src.services.notifications.mock import MockNotifier

        return MockNotifier()
    if nome == "webhook":
        from src.services.notifications.webhook import WebhookNotifier

        return WebhookNotifier()
    if nome == "telegram":
        from src.services.notifications.telegram import TelegramNotifier

        return TelegramNotifier()
    if nome == "email":
        from src.services.notifications.email import EmailNotifier

        return EmailNotifier()

    raise ValueError(f"Notificador desconhecido: {nome!r}")
