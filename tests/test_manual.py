"""Testes da inclusão de prazos manuais."""
from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from src.models import PrazoManual, TipoPrazo
from src.services.agenda.mock import MockAgendaProvider
from src.services.manual import construir_analise_manual, registrar_prazo_manual

# 2026-06-19 é uma sexta-feira (base das contagens).
SEXTA = date(2026, 6, 19)


def test_prazo_manual_por_dias_uteis_calcula_data_fatal() -> None:
    pm = PrazoManual(
        tipo=TipoPrazo.MANIFESTACAO,
        descricao="Manifestar sobre documentos",
        prazo_dias=5,
        data_base=SEXTA,
    )
    analise = construir_analise_manual(pm)

    # 5 dias úteis a partir de sexta 19/06 -> sexta 26/06.
    assert analise.prazos[0].data_fatal == date(2026, 6, 26)
    assert analise.id_externo.startswith("manual-")
    assert analise.possui_prazo is True


def test_prazo_manual_com_data_fatal_direta() -> None:
    pm = PrazoManual(
        tipo=TipoPrazo.AUDIENCIA, descricao="Audiência", data_fatal=date(2026, 8, 1)
    )
    analise = construir_analise_manual(pm)
    assert analise.prazos[0].data_fatal == date(2026, 8, 1)


def test_prazo_manual_dias_corridos() -> None:
    pm = PrazoManual(
        descricao="Prazo material", prazo_dias=10, data_base=SEXTA, dias_uteis=False
    )
    analise = construir_analise_manual(pm)
    assert analise.prazos[0].data_fatal == date(2026, 6, 29)


def test_prazo_manual_exige_data_ou_dias() -> None:
    with pytest.raises(ValidationError):
        PrazoManual(descricao="prazo sem data nem dias")


def test_registrar_prazo_manual_cria_evento() -> None:
    agenda = MockAgendaProvider()
    pm = PrazoManual(
        tipo=TipoPrazo.RECURSO,
        descricao="Interpor apelação",
        prazo_dias=15,
        data_base=SEXTA,
        numero_processo="0001",
    )

    evento = registrar_prazo_manual(pm, agenda=agenda)

    assert evento.data == date(2026, 7, 10)  # 15 dias úteis a partir de 19/06
    assert len(agenda.eventos_criados) == 1
    assert "Recurso" in evento.titulo


def test_idempotencia_chave_estavel() -> None:
    pm = PrazoManual(descricao="igual", data_fatal=date(2026, 8, 1), numero_processo="9")
    a1 = construir_analise_manual(pm)
    a2 = construir_analise_manual(pm)
    # Mesmo conteúdo -> mesma chave (evita evento duplicado na agenda).
    assert a1.id_externo == a2.id_externo
