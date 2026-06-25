"""Testes do módulo de inteligência (Etapa 2) usando o provedor mock."""
from __future__ import annotations

from datetime import date

import pytest

from src.models import (
    AnaliseExtraida,
    FonteCaptura,
    PrazoExtraido,
    Publicacao,
    TipoPrazo,
)
from src.services.intelligence import get_intelligence_provider
from src.services.intelligence.base import IntelligenceProvider
from src.services.intelligence.mock import MockIntelligenceProvider


def _publicacao(conteudo: str, data: date = date(2026, 6, 19)) -> Publicacao:
    return Publicacao(
        id_externo="pub-1",
        fonte=FonteCaptura.OUTRA,
        numero_processo="1001234-56.2024.8.26.0100",
        conteudo=conteudo,
        data_publicacao=data,
    )


def test_mock_extrai_prazo_e_calcula_data_fatal() -> None:
    pub = _publicacao(
        "Fica a parte intimada para apresentar contestação no prazo de 15 "
        "(quinze) dias, sob pena de revelia."
    )
    analise = MockIntelligenceProvider().analisar(pub)

    assert analise.possui_prazo
    assert len(analise.prazos) == 1
    prazo = analise.prazos[0]
    assert prazo.tipo is TipoPrazo.CONTESTACAO
    assert prazo.prazo_dias == 15
    # 15 dias úteis a partir de sexta 19/06/2026 -> sexta 10/07/2026.
    assert prazo.data_fatal == date(2026, 7, 10)
    assert prazo.urgente is True


def test_mock_extrai_audiencia_com_data_explicita() -> None:
    pub = _publicacao(
        "Designo audiência de conciliação para o dia 15/07/2026, às 14h00."
    )
    analise = MockIntelligenceProvider().analisar(pub)

    assert analise.possui_prazo
    prazo = analise.prazos[0]
    assert prazo.tipo is TipoPrazo.AUDIENCIA
    assert prazo.prazo_dias is None
    # Sem prazo em dias: a data fatal é a própria data de referência citada.
    assert prazo.data_fatal == date(2026, 7, 15)


def test_mock_sem_prazo() -> None:
    pub = _publicacao("Mero expediente. Juntada de petição aos autos.")
    analise = MockIntelligenceProvider().analisar(pub)

    assert analise.possui_prazo is False
    assert analise.prazos == []


class _ClienteStubProvider(IntelligenceProvider):
    """Provedor de teste que devolve uma extração com cliente/partes preenchidos."""

    def _extrair(self, publicacao: Publicacao) -> AnaliseExtraida:
        return AnaliseExtraida(
            resumo="intimação",
            cliente="João da Silva",
            parte_contraria="Banco XYZ S.A.",
            possui_prazo=True,
            prazos=[
                PrazoExtraido(
                    tipo=TipoPrazo.CONTESTACAO, descricao="Contestar", prazo_dias=15
                )
            ],
        )


def test_cliente_propaga_para_analise_e_prazo() -> None:
    analise = _ClienteStubProvider().analisar(_publicacao("texto qualquer"))

    # Cliente e parte contrária devem aparecer na análise e em cada prazo.
    assert analise.cliente == "João da Silva"
    assert analise.parte_contraria == "Banco XYZ S.A."
    assert analise.prazos[0].parte_contraria == "Banco XYZ S.A."
    assert analise.prazos[0].cliente == "João da Silva"


class _SemPartesProvider(IntelligenceProvider):
    """IA que não identifica as partes (como o provedor mock por heurística)."""

    def _extrair(self, publicacao: Publicacao) -> AnaliseExtraida:
        return AnaliseExtraida(
            resumo="r",
            possui_prazo=True,
            prazos=[
                PrazoExtraido(tipo=TipoPrazo.OUTRO, descricao="x", prazo_dias=10)
            ],
        )


def test_partes_da_captura_usadas_quando_ia_nao_identifica() -> None:
    # As partes vêm da fonte de captura (DJEN) quando a IA não as identifica.
    pub = Publicacao(
        id_externo="p",
        numero_processo="1",
        conteudo="texto",
        data_publicacao=date(2026, 6, 19),
        cliente="Autor Capturado",
        parte_contraria="Réu Capturado",
    )
    analise = _SemPartesProvider().analisar(pub)
    assert analise.cliente == "Autor Capturado"
    assert analise.parte_contraria == "Réu Capturado"
    assert analise.prazos[0].cliente == "Autor Capturado"
    assert analise.prazos[0].parte_contraria == "Réu Capturado"


def test_factory_retorna_mock() -> None:
    assert isinstance(get_intelligence_provider("mock"), MockIntelligenceProvider)


def test_factory_provedor_desconhecido() -> None:
    with pytest.raises(ValueError):
        get_intelligence_provider("provedor_inexistente")
