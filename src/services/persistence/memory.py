"""Armazenamento de estado em memória (para testes e execuções efêmeras)."""
from __future__ import annotations

from src.services.persistence.base import StateStore


class MemoryStateStore(StateStore):
    """StateStore não-persistente, mantido apenas em memória."""

    def __init__(self) -> None:
        self._publicacoes: set[str] = set()
        self._eventos: dict[str, str | None] = {}

    def publicacao_processada(self, chave: str) -> bool:
        return chave in self._publicacoes

    def registrar_publicacao(self, chave: str) -> None:
        self._publicacoes.add(chave)

    def evento_registrado(self, chave: str) -> bool:
        return chave in self._eventos

    def registrar_evento(self, chave: str, referencia: str | None = None) -> None:
        self._eventos[chave] = referencia
