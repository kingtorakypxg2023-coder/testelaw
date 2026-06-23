"""Interface do armazenamento de estado (persistência).

Registra o que já foi processado/agendado para evitar reprocessar publicações
(economiza chamadas de IA) e criar eventos duplicados na agenda.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class StateStore(ABC):
    """Contrato do armazenamento de estado do monitoramento."""

    @abstractmethod
    def publicacao_processada(self, chave: str) -> bool:
        """Indica se a publicação (por chave) já foi processada."""
        raise NotImplementedError

    @abstractmethod
    def registrar_publicacao(self, chave: str) -> None:
        """Marca uma publicação como processada."""
        raise NotImplementedError

    @abstractmethod
    def evento_registrado(self, chave: str) -> bool:
        """Indica se o evento (por chave de idempotência) já foi criado."""
        raise NotImplementedError

    @abstractmethod
    def registrar_evento(self, chave: str, referencia: str | None = None) -> None:
        """Marca um evento como criado, guardando sua referência (ID)."""
        raise NotImplementedError
