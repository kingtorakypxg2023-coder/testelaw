"""Repositório de prazos manuais (para listar/remover).

Persiste os prazos informados manualmente, com o ID do evento criado na agenda,
permitindo um CRUD básico. Reutiliza o mesmo arquivo SQLite do state store.
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from abc import ABC, abstractmethod
from datetime import date, datetime, timezone

from src.config.settings import settings
from src.models import PrazoManual, PrazoManualRegistro
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ManualPrazoRepository(ABC):
    """Contrato do repositório de prazos manuais."""

    @abstractmethod
    def adicionar(
        self, prazo: PrazoManual, data_fatal: date, evento_ref: str | None = None
    ) -> str:
        """Persiste um prazo manual e retorna seu ID."""
        raise NotImplementedError

    @abstractmethod
    def listar(self) -> list[PrazoManualRegistro]:
        raise NotImplementedError

    @abstractmethod
    def obter(self, id_: str) -> PrazoManualRegistro | None:
        raise NotImplementedError

    @abstractmethod
    def remover(self, id_: str) -> bool:
        raise NotImplementedError


class MemoryManualPrazoRepository(ManualPrazoRepository):
    """Repositório em memória (testes/execuções efêmeras)."""

    def __init__(self) -> None:
        self._dados: dict[str, PrazoManualRegistro] = {}

    def adicionar(self, prazo, data_fatal, evento_ref=None) -> str:
        id_ = uuid.uuid4().hex[:12]
        self._dados[id_] = PrazoManualRegistro(
            id=id_, prazo=prazo, data_fatal=data_fatal, evento_ref=evento_ref
        )
        return id_

    def listar(self) -> list[PrazoManualRegistro]:
        return sorted(self._dados.values(), key=lambda r: r.data_fatal)

    def obter(self, id_: str) -> PrazoManualRegistro | None:
        return self._dados.get(id_)

    def remover(self, id_: str) -> bool:
        return self._dados.pop(id_, None) is not None


class SqliteManualPrazoRepository(ManualPrazoRepository):
    """Repositório persistente em SQLite."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.state_db_path
        diretorio = os.path.dirname(self.db_path)
        if diretorio:
            os.makedirs(diretorio, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prazos_manuais (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                data_fatal TEXT NOT NULL,
                evento_ref TEXT,
                criado_em TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def adicionar(self, prazo, data_fatal, evento_ref=None) -> str:
        id_ = uuid.uuid4().hex[:12]
        self._conn.execute(
            "INSERT INTO prazos_manuais (id, payload, data_fatal, evento_ref, criado_em) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                id_,
                prazo.model_dump_json(),
                data_fatal.isoformat(),
                evento_ref,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()
        return id_

    @staticmethod
    def _to_registro(row: tuple) -> PrazoManualRegistro:
        id_, payload, data_fatal, evento_ref, criado_em = row
        return PrazoManualRegistro(
            id=id_,
            prazo=PrazoManual.model_validate_json(payload),
            data_fatal=date.fromisoformat(data_fatal),
            evento_ref=evento_ref,
            criado_em=datetime.fromisoformat(criado_em),
        )

    def listar(self) -> list[PrazoManualRegistro]:
        cur = self._conn.execute(
            "SELECT id, payload, data_fatal, evento_ref, criado_em "
            "FROM prazos_manuais ORDER BY data_fatal"
        )
        return [self._to_registro(row) for row in cur.fetchall()]

    def obter(self, id_: str) -> PrazoManualRegistro | None:
        cur = self._conn.execute(
            "SELECT id, payload, data_fatal, evento_ref, criado_em "
            "FROM prazos_manuais WHERE id = ?",
            (id_,),
        )
        row = cur.fetchone()
        return self._to_registro(row) if row else None

    def remover(self, id_: str) -> bool:
        cur = self._conn.execute("DELETE FROM prazos_manuais WHERE id = ?", (id_,))
        self._conn.commit()
        return cur.rowcount > 0

    def fechar(self) -> None:
        self._conn.close()


def get_manual_repository(nome: str | None = None) -> ManualPrazoRepository:
    """Retorna o repositório de prazos manuais conforme STATE_STORE."""
    nome = (nome or settings.state_store).strip().lower()
    if nome in ("memory", "mem", "memoria"):
        return MemoryManualPrazoRepository()
    if nome in ("sqlite", "sql", "db"):
        return SqliteManualPrazoRepository()
    raise ValueError(f"Repositório de prazos manuais desconhecido: {nome!r}")
