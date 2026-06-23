"""Fábrica do armazenamento de estado."""
from __future__ import annotations

from src.config.settings import settings
from src.services.persistence.base import StateStore
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_state_store(nome: str | None = None) -> StateStore:
    """Retorna a instância do armazenamento de estado solicitado."""
    nome = (nome or settings.state_store).strip().lower()
    logger.debug("Selecionando armazenamento de estado: %s", nome)

    if nome in ("memory", "mem", "memoria"):
        from src.services.persistence.memory import MemoryStateStore

        return MemoryStateStore()
    if nome in ("sqlite", "sql", "db"):
        from src.services.persistence.sqlite_store import SqliteStateStore

        return SqliteStateStore()

    raise ValueError(f"Armazenamento de estado desconhecido: {nome!r}")
