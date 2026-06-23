"""Fábrica de provedores de agenda."""
from __future__ import annotations

from src.config.settings import settings
from src.services.agenda.base import AgendaProvider
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_agenda_provider(nome: str | None = None) -> AgendaProvider:
    """Retorna a instância do provedor de agenda solicitado."""
    nome = (nome or settings.agenda_provider).strip().lower()
    logger.debug("Selecionando provedor de agenda: %s", nome)

    if nome in ("mock", "fake", "stub", "log"):
        from src.services.agenda.mock import MockAgendaProvider

        return MockAgendaProvider()
    if nome in ("google", "google_calendar", "calendar"):
        from src.services.agenda.google_calendar import GoogleCalendarProvider

        return GoogleCalendarProvider()

    raise ValueError(f"Provedor de agenda desconhecido: {nome!r}")
