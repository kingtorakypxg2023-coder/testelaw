"""Testes da persistência de prazos capturados (para a lista unificada)."""
from __future__ import annotations

from datetime import date

from src.models import AnalisePublicacao, Prazo, TipoPrazo
from src.services.manual import listar_prazos_manuais, salvar_prazos_capturados
from src.services.manual.repository import MemoryManualPrazoRepository


def _analise() -> AnalisePublicacao:
    return AnalisePublicacao(
        id_externo="pub-9",
        numero_processo="1001234-56.2024.8.26.0100",
        cliente="Maria Souza",
        resumo="resumo",
        possui_prazo=True,
        prazos=[
            Prazo(
                tipo=TipoPrazo.RECURSO,
                descricao="Interpor apelação",
                cliente="Maria Souza",
                prazo_dias=15,
                data_fatal=date(2026, 7, 10),
                urgente=True,
            )
        ],
    )


def test_salvar_prazos_capturados_idempotente() -> None:
    repo = MemoryManualPrazoRepository()

    n1 = salvar_prazos_capturados([_analise()], repository=repo)
    n2 = salvar_prazos_capturados([_analise()], repository=repo)  # mesma chave -> dedup

    assert n1 == 1
    assert n2 == 0
    lista = listar_prazos_manuais(repository=repo)
    assert len(lista) == 1
    assert lista[0].origem == "captura"
    assert lista[0].prazo.descricao == "Interpor apelação"
    assert lista[0].prazo.cliente == "Maria Souza"  # cliente preservado na captura
    assert lista[0].data_fatal == date(2026, 7, 10)


def test_salvar_prazos_ignora_sem_data_fatal() -> None:
    repo = MemoryManualPrazoRepository()
    analise = AnalisePublicacao(
        id_externo="x",
        resumo="r",
        prazos=[Prazo(tipo=TipoPrazo.OUTRO, descricao="sem data", data_fatal=None)],
    )
    assert salvar_prazos_capturados([analise], repository=repo) == 0
    assert listar_prazos_manuais(repository=repo) == []


def test_lista_ordenada_por_data_e_tipo() -> None:
    from src.models import PrazoManual

    repo = MemoryManualPrazoRepository()
    # Mesma data fatal, tipos diferentes -> deve ordenar por tipo dentro da data.
    repo.adicionar(PrazoManual(tipo=TipoPrazo.RECURSO, descricao="r", data_fatal=date(2026, 7, 1)), date(2026, 7, 1))
    repo.adicionar(PrazoManual(tipo=TipoPrazo.CONTESTACAO, descricao="c", data_fatal=date(2026, 7, 1)), date(2026, 7, 1))
    repo.adicionar(PrazoManual(tipo=TipoPrazo.AUDIENCIA, descricao="a", data_fatal=date(2026, 6, 20)), date(2026, 6, 20))

    lista = listar_prazos_manuais(repository=repo)
    chaves = [(r.data_fatal.isoformat(), r.prazo.tipo.value) for r in lista]
    assert chaves == [
        ("2026-06-20", "audiencia"),
        ("2026-07-01", "contestacao"),  # contestacao antes de recurso (ordem alfabética)
        ("2026-07-01", "recurso"),
    ]


def test_lista_unifica_manual_e_capturado() -> None:
    repo = MemoryManualPrazoRepository()
    # captura
    salvar_prazos_capturados([_analise()], repository=repo)
    # manual
    from src.models import PrazoManual

    repo.adicionar(
        PrazoManual(descricao="Manual X", data_fatal=date(2026, 6, 30)),
        date(2026, 6, 30),
        origem="manual",
    )
    lista = listar_prazos_manuais(repository=repo)
    origens = sorted(r.origem for r in lista)
    assert origens == ["captura", "manual"]
    # ordenado por data fatal (30/06 antes de 10/07)
    assert lista[0].data_fatal == date(2026, 6, 30)
