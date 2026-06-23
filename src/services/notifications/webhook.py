"""Notificador via webhook HTTP (compatível com Slack/Discord/custom)."""
from __future__ import annotations

import requests

from src.config.settings import settings
from src.services.notifications.base import Notifier, NotifierError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WebhookNotifier(Notifier):
    """Envia a notificação como POST JSON para uma URL de webhook."""

    def __init__(self, url: str | None = None, timeout: int = 15) -> None:
        self.url = url or settings.webhook_url
        if not self.url:
            raise NotifierError("WEBHOOK_URL não configurada.")
        self.timeout = timeout

    def enviar(self, titulo: str, mensagem: str, *, urgente: bool = False) -> bool:
        payload = {
            "titulo": titulo,
            "mensagem": mensagem,
            "urgente": urgente,
            # 'text' cobre webhooks de Slack/Discord que esperam esse campo.
            "text": f"{titulo}\n{mensagem}",
        }
        try:
            resp = requests.post(self.url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise NotifierError(f"Falha ao enviar webhook: {exc}") from exc
        return True
