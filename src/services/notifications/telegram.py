"""Notificador via Telegram Bot API."""
from __future__ import annotations

import requests

from src.config.settings import settings
from src.services.notifications.base import Notifier, NotifierError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TelegramNotifier(Notifier):
    """Envia a notificação como mensagem de um bot do Telegram."""

    def __init__(
        self,
        token: str | None = None,
        chat_id: str | None = None,
        timeout: int = 15,
    ) -> None:
        self.token = token or settings.telegram_bot_token
        self.chat_id = chat_id or settings.telegram_chat_id
        if not self.token or not self.chat_id:
            raise NotifierError(
                "TELEGRAM_BOT_TOKEN e/ou TELEGRAM_CHAT_ID não configurados."
            )
        self.timeout = timeout

    def enviar(self, titulo: str, mensagem: str, *, urgente: bool = False) -> bool:
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        texto = f"*{titulo}*\n{mensagem}"
        try:
            resp = requests.post(
                url,
                json={"chat_id": self.chat_id, "text": texto, "parse_mode": "Markdown"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise NotifierError(f"Falha ao enviar Telegram: {exc}") from exc
        return True
