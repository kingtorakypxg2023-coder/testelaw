"""Interface comum dos notificadores (alertas além da agenda).

Permite enviar alertas de prazos (especialmente os urgentes) por webhook
(Slack/Discord/custom), Telegram ou e-mail. O formato da mensagem é comum a
todos os canais (`formatar_evento`).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.models import EventoAgenda


class NotifierError(Exception):
    """Erro de configuração ou envio de notificação."""


def formatar_evento(evento: EventoAgenda) -> tuple[str, str]:
    """Formata um evento como (título, corpo) para notificação."""
    titulo = ("🔴 " if evento.urgente else "🗓️ ") + evento.titulo
    corpo = (
        f"{evento.titulo}\n"
        f"Data fatal: {evento.data.strftime('%d/%m/%Y')}\n"
        f"Lembrete: {evento.lembrete_dias_antes} dia(s) antes\n\n"
        f"{evento.descricao}"
    )
    return titulo, corpo


class Notifier(ABC):
    """Contrato dos notificadores."""

    @abstractmethod
    def enviar(self, titulo: str, mensagem: str, *, urgente: bool = False) -> bool:
        """Envia uma notificação. Retorna True em caso de sucesso."""
        raise NotImplementedError

    def notificar_evento(self, evento: EventoAgenda) -> bool:
        titulo, corpo = formatar_evento(evento)
        return self.enviar(titulo, corpo, urgente=evento.urgente)

    def notificar_eventos(self, eventos: list[EventoAgenda]) -> list[bool]:
        return [self.notificar_evento(evento) for evento in eventos]
