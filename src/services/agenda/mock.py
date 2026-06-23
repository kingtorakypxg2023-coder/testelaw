"""Provedor de agenda *mock* para desenvolvimento e testes.

Registra (em log e em memória) os eventos que seriam criados, sem chamar
nenhuma API externa. Permite rodar o pipeline completo sem credenciais.
"""
from __future__ import annotations

from src.models import EventoAgenda
from src.services.agenda.base import AgendaProvider
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MockAgendaProvider(AgendaProvider):
    """Simula a criação de eventos de agenda."""

    def __init__(self) -> None:
        self.eventos_criados: list[EventoAgenda] = []

    def criar_evento(self, evento: EventoAgenda) -> str | None:
        self.eventos_criados.append(evento)
        logger.info(
            "[MOCK-AGENDA] Evento '%s' em %s (lembrete %d dia(s) antes) | chave=%s",
            evento.titulo,
            evento.data.isoformat(),
            evento.lembrete_dias_antes,
            evento.chave_idempotencia,
        )
        return f"mock-evento-{len(self.eventos_criados)}"
