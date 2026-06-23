"""Notificador via e-mail (SMTP, stdlib)."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from src.config.settings import settings
from src.services.notifications.base import Notifier, NotifierError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EmailNotifier(Notifier):
    """Envia a notificação por e-mail via servidor SMTP (com STARTTLS)."""

    def __init__(self, timeout: int = 20) -> None:
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.usuario = settings.smtp_user
        self.senha = settings.smtp_password
        self.remetente = settings.smtp_from or settings.smtp_user
        self.destinatario = settings.smtp_to
        self.timeout = timeout
        if not self.host or not self.remetente or not self.destinatario:
            raise NotifierError(
                "Configuração de e-mail incompleta (SMTP_HOST/SMTP_FROM/SMTP_TO)."
            )

    def enviar(self, titulo: str, mensagem: str, *, urgente: bool = False) -> bool:
        msg = EmailMessage()
        msg["Subject"] = ("[URGENTE] " if urgente else "") + titulo
        msg["From"] = self.remetente
        msg["To"] = self.destinatario
        msg.set_content(mensagem)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as smtp:
                smtp.starttls()
                if self.usuario and self.senha:
                    smtp.login(self.usuario, self.senha)
                smtp.send_message(msg)
        except (smtplib.SMTPException, OSError) as exc:
            raise NotifierError(f"Falha ao enviar e-mail (SMTP): {exc}") from exc
        return True
