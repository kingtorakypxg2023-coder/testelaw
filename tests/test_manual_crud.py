"""Testes do CRUD de prazos manuais."""
from __future__ import annotations

from datetime import date

import pytest

from src.models import PrazoManual, TipoPrazo
from src.services.agenda.mock import MockAgendaProvider
from src.services.manual import (
    adicionar_prazo_manual,
    listar_prazos_manuais,
    remover_prazo_manual,
)
from src.services.manual.repository import (
    MemoryManualPrazoRepository,
    SqliteManualPrazoRepository,
    get_manual_repository,
)

SEXTA = date(2026, 6, 19)


def test_adicionar_e_listar() -> None:
    repo = MemoryManualPrazoRepository()
    agenda = MockAgendaProvider()
    pm = PrazoManual(descricao="Protocolar petição", prazo_dias=5, data_base=SEXTA)

    registro = adicionar_prazo_manual(pm, repository=repo, agenda=agenda)

    assert registro.id
    assert registro.data_fatal == date(2026, 6, 26)  # 5 dias úteis de sexta 19/06
    assert registro.evento_ref is not None  # evento criado na agenda mock

    lista = listar_prazos_manuais(repository=repo)
    assert len(lista) == 1
    assert lista[0].id == registro.id


def test_remover() -> None:
    repo = MemoryManualPrazoRepository()
    agenda = MockAgendaProvider()
    pm = PrazoManual(tipo=TipoPrazo.AUDIENCIA, descricao="Audiência", data_fatal=date(2026, 8, 1))
    registro = adicionar_prazo_manual(pm, repository=repo, agenda=agenda)

    assert remover_prazo_manual(registro.id, repository=repo, agenda=agenda) is True
    assert listar_prazos_manuais(repository=repo) == []
    # Remover algo inexistente retorna False.
    assert remover_prazo_manual("inexistente", repository=repo, agenda=agenda) is False


def test_sqlite_repo_persiste(tmp_path) -> None:
    db = str(tmp_path / "manual.db")
    repo = SqliteManualPrazoRepository(db_path=db)
    pm = PrazoManual(descricao="Persistido", data_fatal=date(2026, 8, 1), numero_processo="9")

    id_ = repo.adicionar(pm, date(2026, 8, 1), "ref-1")
    repo.fechar()

    repo2 = SqliteManualPrazoRepository(db_path=db)
    registro = repo2.obter(id_)
    assert registro is not None
    assert registro.prazo.descricao == "Persistido"
    assert registro.evento_ref == "ref-1"
    assert len(repo2.listar()) == 1
    assert repo2.remover(id_) is True
    assert repo2.listar() == []
    repo2.fechar()


def test_factory_memory() -> None:
    assert isinstance(get_manual_repository("memory"), MemoryManualPrazoRepository)


def test_factory_desconhecido() -> None:
    with pytest.raises(ValueError):
        get_manual_repository("xpto")
