"""Testes do armazenamento de estado (persistência)."""
from __future__ import annotations

import pytest

from src.services.persistence import get_state_store
from src.services.persistence.memory import MemoryStateStore
from src.services.persistence.sqlite_store import SqliteStateStore


def test_memory_store_dedup() -> None:
    store = MemoryStateStore()

    assert store.publicacao_processada("a") is False
    store.registrar_publicacao("a")
    assert store.publicacao_processada("a") is True

    assert store.evento_registrado("e1") is False
    store.registrar_evento("e1", "ref-1")
    assert store.evento_registrado("e1") is True


def test_sqlite_store_persiste_entre_conexoes(tmp_path) -> None:
    db = tmp_path / "estado.db"

    store = SqliteStateStore(db_path=str(db))
    store.registrar_publicacao("pub-1")
    store.registrar_evento("ev-1", "ref-1")
    store.registrar_publicacao("pub-1")  # idempotente: não deve duplicar/erro
    store.fechar()

    # Reabrir o mesmo arquivo: o estado deve persistir.
    store2 = SqliteStateStore(db_path=str(db))
    assert store2.publicacao_processada("pub-1") is True
    assert store2.evento_registrado("ev-1") is True
    assert store2.publicacao_processada("inexistente") is False
    store2.fechar()


def test_factory_memory() -> None:
    assert isinstance(get_state_store("memory"), MemoryStateStore)


def test_factory_desconhecido() -> None:
    with pytest.raises(ValueError):
        get_state_store("provedor_inexistente")
