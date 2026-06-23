"""Interface comum dos provedores de agenda/alertas (Etapa 3)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.models import EventoAgenda


class AgendaError(Exception):
    """Erro ao integrar com a agenda (credencial, rede, API)."""


class AgendaProvider(ABC):
    """Contrato dos provedores de agenda (Google Calendar, mock, ...)."""

    @abstractmethod
    def criar_evento(self, evento: EventoAgenda) -> str | None:
        """Cria um evento e devolve sua referência/ID (ou None se ignorado)."""
        raise NotImplementedError

    def criar_eventos(self, eventos: list[EventoAgenda]) -> list[str | None]:
        """Cria vários eventos, devolvendo a referência de cada um."""
        return [self.criar_evento(evento) for evento in eventos]
