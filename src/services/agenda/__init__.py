"""Etapa 3 - INTEGRAÇÃO / AGENDA.

Criação de eventos no Google Calendar (e/ou alertas) a partir dos prazos
estruturados extraídos na Etapa 2. Cada prazo com data fatal vira um evento
com lembrete de antecedência configurável (`DEADLINE_REMINDER_DAYS`).

Uso típico::

    from src.services.agenda import get_agenda_provider, montar_eventos

    eventos = montar_eventos(analises, settings.deadline_reminder_days)
    get_agenda_provider().criar_eventos(eventos)
"""
from src.services.agenda.base import AgendaError, AgendaProvider
from src.services.agenda.eventos import montar_eventos
from src.services.agenda.factory import get_agenda_provider

__all__ = [
    "AgendaError",
    "AgendaProvider",
    "get_agenda_provider",
    "montar_eventos",
]
