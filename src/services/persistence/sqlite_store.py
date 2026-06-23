"""Armazenamento de estado persistente em SQLite (stdlib)."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

from src.config.settings import settings
from src.services.persistence.base import StateStore


class SqliteStateStore(StateStore):
    """StateStore persistente baseado em um arquivo SQLite."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.state_db_path
        diretorio = os.path.dirname(self.db_path)
        if diretorio:
            os.makedirs(diretorio, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._criar_tabelas()

    def _criar_tabelas(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS publicacoes_processadas (
                chave TEXT PRIMARY KEY,
                criado_em TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS eventos_criados (
                chave TEXT PRIMARY KEY,
                referencia TEXT,
                criado_em TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    @staticmethod
    def _agora() -> str:
        return datetime.now(timezone.utc).isoformat()

    def publicacao_processada(self, chave: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM publicacoes_processadas WHERE chave = ?", (chave,)
        )
        return cur.fetchone() is not None

    def registrar_publicacao(self, chave: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO publicacoes_processadas (chave, criado_em) VALUES (?, ?)",
            (chave, self._agora()),
        )
        self._conn.commit()

    def evento_registrado(self, chave: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM eventos_criados WHERE chave = ?", (chave,)
        )
        return cur.fetchone() is not None

    def registrar_evento(self, chave: str, referencia: str | None = None) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO eventos_criados (chave, referencia, criado_em) VALUES (?, ?, ?)",
            (chave, referencia, self._agora()),
        )
        self._conn.commit()

    def fechar(self) -> None:
        self._conn.close()
